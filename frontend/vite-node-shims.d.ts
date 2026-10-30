/** Minimal Node builtin types used by vite.config.ts; no runtime dependency added. */
declare const process: { cwd(): string; env: Record<string, string | undefined> };

declare module "node:crypto" {
  export function createHash(algorithm: string): {
    update(data: string | Uint8Array): ReturnType<typeof createHash>;
    digest(encoding: "hex"): string;
  };
}

declare module "node:fs" {
  export function readFileSync(path: string): Uint8Array;
  export function readdirSync(path: string, options: { withFileTypes: true }): Array<{
    name: string;
    isDirectory(): boolean;
  }>;
}

declare module "node:path" {
  export function join(...segments: string[]): string;
  export function relative(from: string, to: string): string;
}
