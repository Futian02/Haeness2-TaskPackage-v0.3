import * as React from "react";
import { cn } from "../../lib/utils";
export function Badge({className,variant="default",...props}:React.HTMLAttributes<HTMLSpanElement>&{variant?:"default"|"outline"}){return <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",variant==="default"?"border-transparent bg-primary text-primary-foreground":"border-current bg-transparent",className)} {...props}/>}
