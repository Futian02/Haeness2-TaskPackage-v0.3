import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConversationThreadList from "./ConversationThreadList";
import type { Conversation } from "./api";

afterEach(cleanup);

describe("conversation archive action", () => {
  it("offers a real archive affordance without triggering a thread switch", () => {
    const item = {
      id: "conv-demo",
      title: "待移出的历史会话",
      created_at: "2026-10-28T10:00:00Z",
      updated_at: "2026-10-28T10:00:00Z",
      archived_at: null,
    } as Conversation;
    const onArchive = vi.fn();
    const onSelect = vi.fn();
    render(<ConversationThreadList items={[item]} selected={item.id}
      onSelect={onSelect} onCreate={vi.fn()} onRename={vi.fn()} onArchive={onArchive}/>);
    fireEvent.click(screen.getByRole("button", {name: /移出列表 待移出的历史会话/}));
    expect(onArchive).toHaveBeenCalledWith(item);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
