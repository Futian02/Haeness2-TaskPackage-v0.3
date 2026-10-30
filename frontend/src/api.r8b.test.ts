import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

const cid="session/one";
const ok=(body:unknown)=>({ok:true,status:200,json:async()=>body,text:async()=>""}) as Response;
afterEach(()=>vi.restoreAllMocks());

describe("R8B local conversation/file API contracts",()=>{
 it("lists persisted conversations",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok([])));expect(await api.listConversations()).toEqual([]);expect(fetch).toHaveBeenCalledWith("/api/conversations",expect.anything())});
 it("loads one conversation with encoded id",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({id:cid,messages:[]})));await api.getConversation(cid);expect(fetch).toHaveBeenCalledWith("/api/conversations/session%2Fone",expect.anything())});
 it("creates a conversation",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({id:"x"})));await api.createConversation();expect((fetch as any).mock.calls[0][1].method).toBe("POST")});
 it("renames a conversation without changing storage provider",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({title:"new"})));await api.renameConversation("x","new");expect(fetch).toHaveBeenCalledWith("/api/conversations/x",expect.objectContaining({method:"PATCH"}))});
 it("archives through additive API",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({archived_at:"now"})));await api.archiveConversation("x");expect(JSON.parse((fetch as any).mock.calls[0][1].body)).toEqual({archived:true})});
 it("creates a RULE_DEMO run with file ids in JSON snapshot input",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({run_id:"r"})));await api.createRun("x",{question:"q",equipment:"",equipment_type:"",material:"",medium:[],operating_condition:"",field_evidence:"",mode:"RULE_DEMO",file_ids:["f"]});expect(JSON.parse((fetch as any).mock.calls[0][1].body).file_ids).toEqual(["f"])});
 it("does not assign a JSON content type to multipart bodies",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({files:[]})));await api.uploadFiles("x",[new File(["a"],"a.txt")]);expect((fetch as any).mock.calls[0][1].headers).toBeUndefined()});
 it("posts multipart under the selected conversation scope",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({files:[]})));await api.uploadFiles(cid,[new File(["a"],"a.txt")]);expect(fetch).toHaveBeenCalledWith("/api/conversations/session%2Fone/files",expect.objectContaining({method:"POST",body:expect.any(FormData)}))});
 it("rejects a client batch over five files",async()=>{vi.stubGlobal("fetch",vi.fn());await expect(api.uploadFiles("x",Array.from({length:7},(_,i)=>new File(["x"],`${i}.txt`)))).rejects.toThrow("最多选择 5");expect(fetch).not.toHaveBeenCalled()});
 it("lists files in their conversation",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({files:[{id:"f"}]})));expect(await api.listFiles("x")).toEqual([{id:"f"}])});
 it("requests preview through scoped route",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({status:"text_preview"})));await api.previewFile("c","f");expect(fetch).toHaveBeenCalledWith("/api/conversations/c/files/f/preview",expect.anything())});
 it("loads immutable server run-input snapshot",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({question:"q",context:{}})));expect(await api.runInput("run")).toMatchObject({question:"q"})});
 it("rejects failed upload responses with HTTP status",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false,status:415,text:async()=>"bad type"}));await expect(api.uploadFiles("c",[new File(["x"],"x.exe")])).rejects.toThrow("415")});
 it("uses browser FormData boundary generation",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue(ok({files:[]})));await api.uploadFiles("c",[new File(["x"],"x.md")]);expect((fetch as any).mock.calls[0][1].headers).toBeUndefined()});
});
