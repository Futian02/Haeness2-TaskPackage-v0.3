import { useLayoutEffect, useRef, useState } from "react";
import { ReactFlow, Background, Controls, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export default function AgentFlow({nodes,edges}:{nodes:Node[];edges:Edge[]}){
 const host=useRef<HTMLDivElement>(null);const [measured,setMeasured]=useState(false);
 useLayoutEffect(()=>{const element=host.current;if(!element)return;let frame=0;const update=()=>{const visible=element.clientWidth>0&&element.clientHeight>0;setMeasured(previous=>previous===visible?previous:visible)};update();const observer=new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(update)});observer.observe(element);return()=>{cancelAnimationFrame(frame);observer.disconnect()}},[]);
 return <div ref={host} className="agent-flow-canvas">{measured&&<ReactFlow nodes={nodes} edges={edges} style={{width:"100%",height:"100%"}} fitView fitViewOptions={{padding:0.12}} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}>
   <Background color="var(--line)" gap={18}/><Controls showInteractive={false}/>
 </ReactFlow>}</div>;
}
