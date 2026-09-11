import { redirect } from "next/navigation";

// Redirige a /tickets si hay sesión activa, o a /login si no.
// Por ahora redirige siempre a /login hasta que se implemente la autenticación.
export default function RootPage() {
  redirect("/login");
}
