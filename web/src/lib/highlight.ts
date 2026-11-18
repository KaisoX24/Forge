import { createHighlighterCore } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";
import python from "shiki/langs/python.mjs";
import json from "shiki/langs/json.mjs";
import bash from "shiki/langs/bash.mjs";
import githubLight from "shiki/themes/github-light.mjs";

const ALIASES: Record<string, string> = { py: "python", sh: "bash", shell: "bash" };
const KNOWN = new Set(["python", "json", "bash"]);

// Built once, shared by every code block.
const highlighterPromise = createHighlighterCore({
  themes: [githubLight],
  langs: [python, json, bash],
  engine: createJavaScriptRegexEngine(),
});

export async function highlight(code: string, lang: string): Promise<string> {
  const h = await highlighterPromise;
  const name = ALIASES[lang.toLowerCase()] ?? lang.toLowerCase();
  return h.codeToHtml(code, {
    lang: KNOWN.has(name) ? name : "text",
    theme: "github-light",
  });
}