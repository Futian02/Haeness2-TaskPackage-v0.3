import * as React from "react";
import { cn } from "../../lib/utils";
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default"|"outline"|"ghost"; size?: "default"|"sm"|"icon" };
export function Button({className,variant="default",size="default",...props}:Props){return <button className={cn("inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",variant==="default"?"bg-primary text-primary-foreground hover:opacity-90":variant==="outline"?"border border-input bg-background hover:bg-accent":"hover:bg-accent",size==="default"?"h-9 px-4 py-2":size==="sm"?"h-8 px-3":"h-9 w-9",className)} {...props}/>}
