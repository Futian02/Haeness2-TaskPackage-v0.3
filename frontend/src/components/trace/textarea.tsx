import { forwardRef, type ComponentPropsWithoutRef } from "react";

export const Textarea = forwardRef<HTMLTextAreaElement, ComponentPropsWithoutRef<"textarea">>(function TraceTextarea(props, ref) {
  return <textarea ref={ref} {...props} />;
});
