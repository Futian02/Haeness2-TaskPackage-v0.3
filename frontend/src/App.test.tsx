import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

vi.mock("./api",async()=>{
 const actual=await vi.importActual<typeof import("./api")>("./api");
 return {...actual,api:{health:vi.fn().mockResolvedValue({status:"ok",mode:"RULE_DEMO",database:"local.sqlite",teacher_tools:["rbi_lookup"]}),listConversations:vi.fn().mockResolvedValue([]),createConversation:vi.fn().mockResolvedValue({id:"c1",title:"新对话",created_at:new Date().toISOString(),updated_at:new Date().toISOString()}),getConversation:vi.fn().mockResolvedValue({id:"c1",title:"新对话",created_at:"",updated_at:"",messages:[]}),createRun:vi.fn(),replay:vi.fn()},consumeRun:vi.fn()};
});

beforeEach(()=>localStorage.clear());
afterEach(cleanup);
describe("workspace shell",()=>{
 it("shows honest RULE_DEMO label, mobile tabs, and no invented evidence",async()=>{
   render(<App/>);
   await waitFor(()=>expect(screen.getByText("RULE_DEMO")).toBeInTheDocument());
   fireEvent.click(screen.getByRole("button",{name:"展开证据审查"}));
   expect(screen.getByText("证据与复核")).toBeInTheDocument();
   expect(screen.getByText(/未收到来源证据时不推断风险/)).toBeInTheDocument();
   expect(screen.getByRole("button",{name:"审查"})).toBeInTheDocument();
 });
 it("lets the user switch color themes",async()=>{
   render(<App/>);
   fireEvent.click(screen.getAllByRole("button",{name:"切换深浅色"})[0]);
   expect(document.documentElement.dataset.theme).toBe("dark");
 });
 it("exposes explicit structured context fields instead of inventing engineering inputs",async()=>{
   render(<App/>);
   fireEvent.click(screen.getAllByRole("button",{name:/设备与工况/})[0]);
   expect(screen.getByRole("textbox",{name:"材质"})).toBeInTheDocument();
   expect(screen.getByRole("textbox",{name:"现场证据"})).toBeInTheDocument();
 });
});
