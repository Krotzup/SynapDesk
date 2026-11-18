import Link from "next/link";
import { buttonClassName } from "@/components/ui/Button";

// La aprobación MVP02 (contrato frontend–backend) no concede administración de usuarios:
// no hay rutas para listarlos, invitarlos, cambiar su rol ni desactivarlos. Hasta que se
// apruebe, la pantalla solo lo informa, sin datos ni acciones de ejemplo.
export default function AdminPage() {
  return (
    <div className="px-4 py-6 sm:p-6 lg:p-8 bg-[#F8FAFC] min-h-full">
      <div className="max-w-xl mx-auto mt-4 sm:mt-16 bg-white p-6 sm:p-8 rounded-2xl border border-[#E2E8F0] shadow-sm text-center space-y-4">
        <span className="inline-block rounded-full bg-[#E0E7FF] px-3 py-1 text-xs font-semibold text-[#4338CA]">
          Próximamente
        </span>
        <h1 className="text-lg font-bold text-[#0F172A]">Administración de usuarios</h1>
        <p className="text-sm text-[#64748B]">
          La gestión de usuarios, roles y estado de las cuentas no forma parte de esta versión de
          SynapDesk. Se habilitará cuando se apruebe en el contrato con el backend.
        </p>
        <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-center justify-center gap-4 pt-2">
          <Link href="/inicio" className={buttonClassName()}>
            Ir al inicio
          </Link>
          <Link
            href="/tickets"
            className="inline-flex items-center justify-center min-h-11 sm:min-h-0 text-sm text-[#2563EB] font-medium hover:underline"
          >
            Ver tickets
          </Link>
        </div>
      </div>
    </div>
  );
}
