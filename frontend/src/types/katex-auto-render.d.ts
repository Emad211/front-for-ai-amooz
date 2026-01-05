declare module 'katex/contrib/auto-render' {
  type Delimiter = { left: string; right: string; display: boolean };

  export type RenderMathInElementOptions = {
    delimiters?: Delimiter[];
    throwOnError?: boolean;
    [key: string]: unknown;
  };

  export default function renderMathInElement(element: HTMLElement, options?: RenderMathInElementOptions): void;
}
