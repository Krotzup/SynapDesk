import { redirect } from "next/navigation";

// El panel verifica la sesión y, si no hay una válida, lleva al login.
export default function RootPage() {
  redirect("/inicio");
}
