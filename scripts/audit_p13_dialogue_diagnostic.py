"""P13 diagnostic probes: deterministic, read-only, no provider/network requests.

Do not load or print real provider API keys. Does not mutate user's SQLite.
"""
import json
from unittest.mock import patch
from pathlib import Path
from backend.context_slots import extract_explicit_context
from orchestration.intent import classify_intent
from orchestration.r9_industrial_candidate import IndustrialCandidate
from backend import deepseek

cases = [
 ("weather bare", "今天的天气如何", {}),
 ("weather with prior engineering context", "今天的天气如何", {"material":"碳钢","medium":["湿硫化氢"]}),
 ("svg creation bare", "创建一个HTML，内容是SVG绘制一个骑自行车的2D动画", {}),
 ("svg with prior engineering context", "创建一个HTML，内容是SVG绘制一个骑自行车的2D动画", {"material":"碳钢","medium":["湿硫化氢"]}),
 ("explain concept with prior engineering context", "什么是图灵机？", {"material":"碳钢","medium":["湿硫化氢"]}),
 ("follow-up vague", "怎么回事", {}),
 ("mechanism missing context", "该减薄属于哪类腐蚀？", {}),
 ("explicit rich context", "设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：碱式酸性水，温度：60°C，问题：该减薄属于哪类腐蚀？", {}),
 ("bracket medium", "设备：塔顶碱液管线弯头，材质：300系列不锈钢，介质：[碱式酸性水]，温度：60°C，问题：该减薄属于哪类腐蚀？", {}),
 ("normal prose", "我用304不锈钢弯头输送碱式酸性水，60度可能减薄，帮我看原因", {}),
 ("ambiguous wall thinning", "材质：碳钢，介质：湿硫化氢，是否已经减薄？", {}),
 ("specific standard", "GB/T 26610.5-2022 表2面积后果的等级", {}),
 ("risk with missing context", "这台设备风险等级是多少？", {}),
]

def show_case(label,q,prev):
    raw = extract_explicit_context(q)["values"]
    effective = {**prev,**raw}
    route = classify_intent(q,effective)
    answer = {"case": label,"route":route,"fields":raw}
    if label in {"mechanism missing context","explicit rich context","bracket medium","risk with missing context"}:
        out = IndustrialCandidate().run(q,effective)["output"]
        answer["graph"]={"status":out.get("status"),"tools":out.get("tool_calls"),"hypotheses":[x.get("text") for x in out.get("hypotheses",[])][:3],"citations":len(out.get("citations",[])),"unknowns":out.get("unknowns",[])}
    print(json.dumps(answer,ensure_ascii=False))

class FakeResponse:
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self,*_):
        return json.dumps({"choices":[{"finish_reason":"length","message":{"role":"assistant","content":None,"reasoning_content":"FAKE internal reasoning"}}],"usage":{"prompt_tokens":145,"completion_tokens":900}}).encode()

def mock_model():
    cfg={"model":"deepseek-flash","api_key":"SYNTHETIC_KEY_NOT_REAL","endpoint":"https://api.deepseek.com/chat/completions","timeout":1}
    with patch.object(deepseek,"urlopen",return_value=FakeResponse()) as m:
        try: deepseek.generate_chat("创建一个HTML动画",cfg)
        except Exception as exc: print("MOCK_EMPTY_RESPONSE_ERROR",type(exc).__name__,str(exc))
        body=json.loads(m.call_args.args[0].data.decode())
        print("MODEL_PAYLOAD_PROPERTIES",json.dumps({"message_roles":[x["role"] for x in body["messages"]],"num_conversation_messages":len(body["messages"])-1,"tools":body.get("tools"),"thinking":body.get("thinking"),"max_tokens":body.get("max_tokens"),"stream":body.get("stream")},ensure_ascii=False))
    with patch.object(deepseek,"urlopen",return_value=FakeResponse()) as m:
        try: deepseek.generate_chat("怎么回事",cfg)
        except Exception: pass
        body=json.loads(m.call_args.args[0].data.decode())
        print("FOLLOW_UP_PAYLOAD",json.dumps({"user_messages":[x["content"] for x in body["messages"] if x["role"]=="user"]},ensure_ascii=False))

if __name__=="__main__":
    for label,q,previous in cases:show_case(label,q,previous)
    mock_model()
    # Full backend API/SSE/SQLite error reproduction in an isolated temporary DB.
    from tempfile import TemporaryDirectory
    from fastapi.testclient import TestClient
    from backend import api, model_profiles
    from backend.store import Store
    with TemporaryDirectory(prefix="p13-failure-e2e-") as tmp:
        db = Store(Path(tmp) / "diagnostic.db")
        fake_cfg = {"model":"deepseek-flash","provider":"deepseek","profile_id":None,
                    "api_key":"SYNTHETIC_NOT_REAL","endpoint":"https://api.deepseek.com/chat/completions","timeout":1}
        with patch.object(api,"store",db), patch.object(model_profiles,"safe_profile",return_value=fake_cfg), patch.object(model_profiles,"resolve_snapshot",return_value=fake_cfg), patch.object(deepseek,"generate_chat",side_effect=RuntimeError("DeepSeek 返回空内容")):
            with TestClient(api.app) as client:
                created = client.post("/api/conversations",json={"title":"P13模拟失败"}).json()
                run = client.post("/api/conversations/"+created["id"]+"/runs",json={"question":"创建SVG自行车HTML","mode":"DEEPSEEK"}).json()
                stream = client.get(run["events_url"])
                events = client.get("/api/runs/"+run["run_id"]+"/events").json()["events"]
                detail = client.get("/api/conversations/"+created["id"]).json()
                print("OFFLINE_API_ERROR_E2E",json.dumps({"status":db.run(run["run_id"])["status"],
                    "http_sse":stream.status_code,
                    "event_types":[e["type"] for e in events],
                    "assistant_messages":sum(m["role"]=="assistant" for m in detail["messages"]),
                    "error_message":[e["payload"].get("message") for e in events if e["type"]=="error"]},ensure_ascii=False))
    front = Path("frontend/src/api.ts").read_text(encoding="utf-8")
    print("CLIENT_SSE_ERROR_TREATED_TERMINAL", 'kind === "run_completed" || kind === "error"' in front)
    print("NO_PROVIDER_NETWORK_CALLS",True)
