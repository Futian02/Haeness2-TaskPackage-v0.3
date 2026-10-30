"""Experimental Chinese lexical retrieval for the 554-clause knowledge base.

Uses Python's SQLite FTS5 trigram tokenizer and built-in BM25 scorer. The
index is in-memory, never edits the upstream files, and exposes NO fourth
teacher-facing tool. This baseline is intentionally separate from the existing
upstream.standard_clause_search so that offline comparisons are meaningful.

Limitations:
* three-character trigram is unsuitable for very short terms (fallback LIKE);
* semantic paraphrases need separate embedding retrieval;
* high retrieval scores never authorize risk or inspection conclusions.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from time import perf_counter
from typing import Any

from app.runtime import UPSTREAM


class SqliteLexicalRetriever:
    """In-memory FTS5(BM25) over canonical clauses.jsonl records."""

    def __init__(self, data_path: Path | None = None):
        data_path = Path(data_path) if data_path else UPSTREAM / "05_提交区" / "clauses.jsonl"
        if not data_path.is_file():
            raise FileNotFoundError(f"标准条款库尚未下载：{data_path}")
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "title, body, clause_id UNINDEXED, kind UNINDEXED,"
            "standard_code UNINDEXED, page UNINDEXED,"
            "tokenize='trigram')"
        )
        rows = []
        with data_path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                item = json.loads(line)
                rows.append(
                    (
                        item["title"], item.get("content_raw") or "",
                        item["clause_id"], item["knowledge_type"],
                        item["standard_code"], int(item["page"]),
                    )
                )
        self.connection.executemany(
            "INSERT INTO docs(title,body,clause_id,kind,standard_code,page)"
            " VALUES(?,?,?,?,?,?)", rows
        )
        self.total = len(rows)

    @staticmethod
    def _match_query(query: str) -> str:
        # FTS5 query syntax requires quote escaping, not string concatenation
        # into SQL. Exact phrases are desirable for formal Chinese terms.
        terms = [p.strip() for p in re.split(r"\s+", query) if len(p.strip()) >= 3]
        return " OR ".join('"' + p.replace('"', '""') + '"' for p in terms)

    def search(self, query: str, kind: str | None = None, top_k: int = 5) -> list[dict[str, Any]]:
        """Return source-bearing hits. Scores are *relative*, not probabilities."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty")
        if kind not in (None, "rbi", "damage_mechanism"):
            raise ValueError(f"invalid kind: {kind!r}")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer in [1, 20]")
        q = self._match_query(query)
        if q:
            sql = (
                "SELECT clause_id,title,kind,standard_code,page,"
                "-bm25(docs,6.0,1.0) AS score "
                "FROM docs WHERE docs MATCH ?"
            )
            params: list[Any] = [q]
            if kind:
                sql += " AND kind = ?"
                params.append(kind)
            sql += " ORDER BY bm25(docs,6.0,1.0) ASC, clause_id ASC LIMIT ?"
            params.append(top_k)
        else:
            sql = (
                "SELECT clause_id,title,kind,standard_code,page,"
                "0.0 AS score FROM docs WHERE (title LIKE ? OR body LIKE ?)"
            )
            params = [f"%{query.strip()}%", f"%{query.strip()}%"]
            if kind:
                sql += " AND kind = ?"
                params.append(kind)
            sql += " ORDER BY title ASC, clause_id ASC LIMIT ?"
            params.append(top_k)
        return [dict(row) for row in self.connection.execute(sql, params)]

    def close(self) -> None:
        self.connection.close()


def timed_search(retriever: SqliteLexicalRetriever, query: str, *, kind: str | None = None,
                 top_k: int = 5) -> tuple[list[dict[str, Any]], float]:
    start = perf_counter()
    result = retriever.search(query, kind=kind, top_k=top_k)
    return result, (perf_counter() - start) * 1000.0
