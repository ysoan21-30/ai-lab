import Navbar from "@/components/Navbar";

export default function PrivacyPage() {
  return (
    <main>
      <Navbar />
      <div className="container-page max-w-3xl py-14">
        <h1 className="text-2xl font-semibold text-slate-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: 2026</p>

        <div className="mt-8 space-y-6 text-sm text-slate-700">
          <section>
            <h2 className="text-base font-semibold text-slate-900">What data is uploaded</h2>
            <p className="mt-1">
              When you use AI Data Profiler, you upload a CSV or Excel file containing your dataset.
              We process this file to compute statistics, detect data-quality issues, and generate an
              ML-readiness report.
            </p>
          </section>
          <section>
            <h2 className="text-base font-semibold text-slate-900">How it is processed</h2>
            <p className="mt-1">
              Your file is parsed and analyzed on our servers using a deterministic statistical
              pipeline (pandas, NumPy, SciPy, scikit-learn). Only aggregated statistics and detected
              issues — never raw rows or individual cell values — are sent to a third-party AI model
              (OpenAI) to generate plain-language insights.
            </p>
          </section>
          <section>
            <h2 className="text-base font-semibold text-slate-900">How long data is retained</h2>
            <p className="mt-1">
              Uploaded files are deleted from our servers immediately after processing completes (or
              after a bounded retention window if processing fails, per our internal cleanup policy).
              The derived statistical report (column statistics, detected issues, scores) is stored in
              your account so you can revisit it later.
            </p>
          </section>
          <section>
            <h2 className="text-base font-semibold text-slate-900">Whether LLM APIs are used</h2>
            <p className="mt-1">
              Yes. We use the OpenAI API to convert the deterministic analysis into a plain-language
              report. If no AI provider is configured, a deterministic rules-based summary is used
              instead. We do not control OpenAI&apos;s internal data handling practices; refer to
              OpenAI&apos;s own privacy policy for details on how they process API requests.
            </p>
          </section>
          <section>
            <h2 className="text-base font-semibold text-slate-900">Whether data is used for model training</h2>
            <p className="mt-1">
              We do not use your uploaded datasets to train our own models. We cannot make
              representations about whether third-party AI providers use API data for training, as
              this depends on their own policies and your account settings with them at the time of
              use.
            </p>
          </section>
          <section>
            <h2 className="text-base font-semibold text-slate-900">How you can delete your data</h2>
            <p className="mt-1">
              You can delete any individual analysis from your dashboard at any time, which removes
              the stored report from our database. To delete your account entirely, contact support.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
