import { useState, type ReactNode } from "react";
import Markdown from "react-markdown";
import { Check, CircleCheck, Copy, ExternalLink, Info, Lightbulb, Target, TriangleAlert } from "lucide-react";
import type { useStep } from "../api/queries";
import HighlightedCode from "./HighlightedCode";

type Step = NonNullable<ReturnType<typeof useStep>["data"]>;
type Lesson = NonNullable<Step["lesson"]>;

function Prose({ children }: { children: string }) {
  return (
    <Markdown
      components={{
        p: ({ children }) => <p className="leading-7 text-slate-600">{children}</p>,
        code: ({ children }) => (
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] text-slate-800">
            {children}
          </code>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-slate-900">{children}</strong>
        ),
        ul: ({ children }) => (
          <ul className="list-disc space-y-1 pl-6 text-slate-700">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal space-y-1 pl-6 text-slate-700">{children}</ol>
        ),
      }}
    >
      {children}
    </Markdown>
  );
}

function CodeBlock({
  title,
  language,
  code,
  output,
}: {
  title?: string | null;
  language?: string | null;
  code: string;
  output?: string | null;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: nothing useful to do.
    }
  }

  return (
    <figure className="overflow-hidden rounded-lg border border-slate-200">
      <figcaption className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-2 text-sm">
        <span className="font-semibold text-slate-800">{title ?? "Example"}</span>
        <span className="flex items-center gap-3 text-xs text-slate-500">
          {language}
          <button
            type="button"
            onClick={copy}
            className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-0.5 hover:bg-slate-100"
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </span>
      </figcaption>
      <HighlightedCode code={code} language={language} />
      {output && (
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-3">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-500">
            Output
          </div>
          <pre className="overflow-x-auto font-mono text-sm text-slate-700">{output}</pre>
        </div>
      )}
    </figure>
  );
}

function Callout({ kind, text }: { kind: string; text: string }) {
  const styles: Record<string, { box: string; icon: ReactNode }> = {
    tip: {
      box: "border-blue-200 bg-blue-50",
      icon: <Lightbulb className="h-5 w-5 text-blue-600" />,
    },
    warning: {
      box: "border-amber-200 bg-amber-50",
      icon: <TriangleAlert className="h-5 w-5 text-amber-600" />,
    },
  };
  const style = styles[kind] ?? {
    box: "border-slate-200 bg-slate-50",
    icon: <Info className="h-5 w-5 text-slate-500" />,
  };
  return (
    <div className={`flex gap-3 rounded-lg border p-4 ${style.box}`}>
      <span className="mt-0.5 shrink-0">{style.icon}</span>
      <Prose>{text}</Prose>
    </div>
  );
}

// Doc labels come with Markdown marks like `FastAPI` or _path operation_.
const plain = (s: string) => s.replace(/[`*_]/g, "");

export default function LessonView({ lesson }: { lesson: Lesson;}) {
  return (
    <div className="max-w-6xl space-y-6">
      <p className="text-lg text-slate-600">{lesson.summary}</p>

      <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-5">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-slate-900">
            <Target className="h-6 w-6 text-blue-600" />
            What you'll learn
          </h2>
          <ul className="space-y-2.5">
            {lesson.you_will_learn.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-slate-800">
                <CircleCheck className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
                {item}
              </li>
            ))}
          </ul>
        </div>

      {lesson.blocks.map((block, i) => {
        switch (block.type) {
          case "text":
            return (
              <section key={i} className="space-y-2">
                {block.heading && <h2 className="text-2xl font-bold text-slate-900">{block.heading}</h2>}
                <Prose>{block.body}</Prose>
              </section>
            );
          case "key_points":
            return (
              <div key={i} className="grid gap-3 sm:grid-cols-2">
                {block.items.map((item) => (
                  <div
                    key={item.title}
                    className="rounded-xl border border-l-4 border-blue-100 border-l-blue-500 bg-blue-50/60 p-4"
                  >
                    <div className="mb-1 font-semibold text-slate-900">{item.title}</div>
                    <Prose>{item.text}</Prose>
                  </div>
                ))}
              </div>
            );
          case "code":
            return (
              <CodeBlock
                key={i}
                title={block.title}
                language={block.language}
                code={block.code}
                output={block.output}
              />
            );
          case "callout":
            return <Callout key={i} kind={block.kind} text={block.text} />;
          default:
            return null;
        }
      })}

      {lesson.docs.length > 0 && (
        <div>
          <h2 className="mb-2 font-bold">Further reading</h2>
          <ul className="space-y-1 text-sm">
            {lesson.docs.map((doc) => (
              <li key={doc.url}>
                <a
                  href={doc.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-blue-700 hover:underline"
                >
                  {plain(doc.label)}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}