import { useEffect, useState } from "react";
import { highlight } from "../lib/highlight";

export default function HighlightedCode({
  code,
  language,
}: {
  code: string;
  language?: string | null;
}) {
  const [html, setHtml] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    highlight(code, language ?? "text")
      .then((result) => {
        if (!cancelled) setHtml(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [code, language]);

  if (html === null) {
    return (
      <pre className="overflow-x-auto bg-white p-4 font-mono text-sm leading-6 text-slate-800">
        {code}
      </pre>
    );
  }
  return (
    <div
      className="shiki-wrap overflow-x-auto bg-white p-4 font-mono text-sm leading-6"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}