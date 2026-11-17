import * as monaco from "monaco-editor";
import Editor,{loader} from "@monaco-editor/react"

// Serve Monaco from our own bundle instead of a CDN, so it works offline
// (a desktop app has no guarantee of internet). Importing only the editor core
// and the Python highlighter keeps the bundle far smaller than "all languages".

loader.config({ monaco });

type Props = {
  path: string; // file name, e.g. "main.py": one editor model per file
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
};

export default function CodeEditor({ path, value, onChange, readOnly = false }: Props) {
  return (
    <Editor
      height="100%"
      path={path}
      language="python"
      theme="vs"
      value={value}
      onChange={(next) => onChange(next ?? "")}
      loading={<p className="p-4 text-sm text-slate-500">Loading editor…</p>}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 14,
        tabSize: 4,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        padding: { top: 12 },
      }}
    />
  );
}