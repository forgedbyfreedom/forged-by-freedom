import {
  AddNewSection,
  ErrorBanner,
  Field,
  SubmitButton,
} from "@/components/ui/form-primitives";
import { importStatements } from "./actions";

export default async function ImportPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; ok?: string }>;
}) {
  const { error, ok } = await searchParams;

  return (
    <div className="space-y-6">
      <header>
        <div className="fbf-eyebrow mb-2">Bulk Import</div>
        <h1 className="text-3xl font-black tracking-tight">Import Transactions</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Drop in your <span className="text-foreground">Venmo</span> or{" "}
          <span className="text-foreground">CashApp</span> CSV exports. We&apos;ll create orders for
          every inbound payment, match the senders to existing clients (or create new ones), and
          skip anything already imported.
        </p>
      </header>

      <ErrorBanner message={error} />
      {ok && (
        <div className="rounded-md border border-success/40 bg-success/10 p-3 text-sm text-success">
          <span className="font-semibold">Imported.</span> {ok}
        </div>
      )}

      <AddNewSection title="Upload CSV Files" defaultOpen={!ok}>
        <form action={importStatements} className="space-y-4">
          <Field
            label="Venmo / CashApp CSV Files"
            required
            hint="Select one or more files. Both formats are auto-detected."
          >
            <input
              name="files"
              type="file"
              accept=".csv,text/csv"
              multiple
              required
              className="block w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1 file:text-xs file:font-bold file:uppercase file:tracking-wider file:text-white hover:file:opacity-90"
            />
          </Field>
          <SubmitButton>Import Transactions</SubmitButton>
        </form>
      </AddNewSection>

      <div className="fbf-card space-y-3 text-sm text-muted-foreground">
        <div className="fbf-eyebrow !text-foreground">How To Export</div>
        <div>
          <span className="font-semibold text-foreground">Venmo:</span> open Venmo on desktop →
          Statements → pick a date range → Download CSV.
        </div>
        <div>
          <span className="font-semibold text-foreground">CashApp:</span> Settings → Statements →
          Export CSV.
        </div>
        <div className="pt-2 text-xs">
          Only <span className="text-foreground">inbound</span> payments are imported. Each
          transaction ID is stored, so re-importing the same statement doesn&apos;t create
          duplicates. Use the Orders page to delete any non-FBF transactions in one click.
        </div>
      </div>
    </div>
  );
}
