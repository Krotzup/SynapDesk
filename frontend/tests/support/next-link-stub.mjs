// Sustituto de "next/link" para las pruebas de componentes: un enlace HTML normal.
import { createElement } from "react";

export default function Link({ href, children, ...props }) {
  // prefetch es propio de Next y no es un atributo HTML.
  const { prefetch, ...attributes } = props;
  void prefetch;
  return createElement(
    "a",
    { href: typeof href === "string" ? href : String(href), ...attributes },
    children
  );
}
