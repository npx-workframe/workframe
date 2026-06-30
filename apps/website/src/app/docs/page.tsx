import { redirect } from "next/navigation";

import { getDefaultDocSlug } from "@/lib/docs";

export default function DocsIndexPage() {
  redirect(`/docs/${getDefaultDocSlug()}`);
}
