import type { ReactNode } from "react";
import type { Language } from "../types";
import { directionFor, localeFor } from "../utils/languages";

interface Props {
  language: Language;
  children: ReactNode;
  as?: "p" | "span" | "div" | "h2" | "h3" | "strong";
  className?: string;
}

/**
 * Renders text in the reading direction of one specific language.
 *
 * Explanation text and the form's own printed labels can be in different scripts at the
 * same time -- an Urdu label read with English guidance, or the reverse -- so direction
 * is set per element rather than on the page. Setting it globally would mirror the other
 * one and make it hard to read.
 */
export function DirectionalText({ language, children, as = "p", className = "" }: Props) {
  const Tag = as;
  const direction = directionFor(language);
  return (
    <Tag
      dir={direction}
      lang={localeFor(language)}
      className={`${direction === "rtl" ? "text-right" : ""} ${className}`.trim()}
    >
      {children}
    </Tag>
  );
}
