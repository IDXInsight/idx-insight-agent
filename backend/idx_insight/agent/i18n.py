"""User-facing text in Indonesian and English.

Every string the agent shows a user comes from this catalogue, so a briefing
is entirely in the user's language. Keys are stable identifiers; values use
``str.format`` placeholders, which must be identical in both languages
(enforced by tests).
"""

from __future__ import annotations

from idx_insight.agent.language import Language

MESSAGES: dict[str, dict[str, str]] = {
    # --- relevance reasons (codes come from analytics.events) --------------------
    "reason.ownership_large": {
        "id": "Perubahan kepemilikan {pct} dari total saham (≥1%)",
        "en": "Ownership change of {pct} of shares outstanding (≥1%)"},
    "reason.ownership_medium": {
        "id": "Perubahan kepemilikan {pct} dari total saham",
        "en": "Ownership change of {pct} of shares outstanding"},
    "reason.large_value": {
        "id": "Nilai transaksi ≥ Rp500 miliar", "en": "Transaction value ≥ IDR 500 bn"},
    "reason.insider": {
        "id": "Transaksi oleh orang dalam (insider)", "en": "Transaction by an insider"},
    "reason.dividend_ex": {
        "id": "Tanggal ex-dividen menentukan hak atas dividen",
        "en": "The ex-dividend date determines who receives the dividend"},
    "reason.dividend_payment": {"id": "Jadwal pembayaran dividen", "en": "Dividend payment date"},
    "reason.agm": {
        "id": "RUPS dapat memutuskan dividen, susunan pengurus, atau aksi korporasi",
        "en": "The shareholders' meeting may decide dividends, management or corporate actions"},
    "reason.stock_split": {
        "id": "Stock split mengubah jumlah dan harga nominal saham",
        "en": "A stock split changes the number of shares and their nominal price"},
    "reason.forward": {
        "id": "Terjadwal di dalam jendela waktu yang diminta",
        "en": "Scheduled within the requested timeframe"},
    "reason.cluster": {
        "id": "Beberapa peristiwa emiten yang sama berdekatan",
        "en": "Several events for the same company close together"},
    "reason.watchlist": {"id": "Emiten ada di watchlist", "en": "Company is on the watchlist"},

    # --- event titles -----------------------------------------------------------------
    "event.holder_default": {"id": "Pemegang saham", "en": "A shareholder"},
    "event.verb.buy": {"id": "membeli", "en": "bought"},
    "event.verb.sell": {"id": "menjual", "en": "sold"},
    "event.verb.other": {"id": "bertransaksi", "en": "traded"},
    "event.filing": {"id": "{holder} {verb} saham {sym}{detail}",
                     "en": "{holder} {verb} shares of {sym}{detail}"},
    "event.filing_pct": {"id": "{pct} saham", "en": "{pct} of shares"},
    "event.filing_value": {"id": "nilai {value}", "en": "value {value}"},
    "event.agm": {"id": "RUPS {sym}", "en": "{sym} shareholders' meeting (AGM)"},
    "event.dividend_ex": {"id": "Ex-dividen {sym} {amount}/saham",
                          "en": "{sym} ex-dividend {amount}/share"},
    "event.dividend_ex_plain": {"id": "Ex-dividen {sym}", "en": "{sym} ex-dividend"},
    "event.dividend_payment": {"id": "Pembayaran dividen {sym}", "en": "{sym} dividend payment"},
    "event.stock_split": {"id": "Stock split {sym} 1:{ratio}", "en": "{sym} stock split 1:{ratio}"},

    # --- discovery ---------------------------------------------------------------------
    "gap.scope_truncated": {
        "id": "Cakupan {n} emiten dibatasi ke {cap} pertama untuk menjaga jumlah tool call.",
        "en": "Scope of {n} companies limited to the first {cap} to bound tool calls."},
    "recovery.widen.action": {
        "id": "Perlebar jendela filing ke {days} hari terakhir (sekali)",
        "en": "Widen the filing window to the last {days} days (once)"},
    "recovery.widen.outcome": {"id": "{n} filing ditemukan", "en": "{n} filings found"},
    "assumption.widened": {
        "id": "Jendela filing diperlebar ke {start} s/d {end} karena jendela awal kosong.",
        "en": "Filing window widened to {start} – {end} because the initial window was empty."},
    "gap.no_report_schedule": {
        "id": "Sectors tidak mendokumentasikan jadwal rilis laporan keuangan mendatang; hanya "
              "tanggal laporan yang sudah terbit yang tersedia.",
        "en": "Sectors does not document upcoming financial-report release dates; only dates "
              "of reports already published are available."},
    "gap.unverified_shape": {
        "id": "Field upcoming_dividend {sym} terisi, tetapi strukturnya belum terverifikasi di "
              "dokumentasi; tidak digunakan.",
        "en": "Field upcoming_dividend for {sym} is populated but its structure is not verified "
              "in the documentation; not used."},
    "what.corporate_actions": {"id": "aksi korporasi {sym}", "en": "corporate actions {sym}"},
    "what.corporate_actions_calendar": {"id": "kalender aksi korporasi",
                                        "en": "corporate actions calendar"},
    "what.filings": {"id": "filing {target}", "en": "filings {target}"},
    "what.company_report": {"id": "company report {sym}", "en": "company report {sym}"},
    "what.quarterly": {"id": "laporan kuartalan {sym}", "en": "quarterly financials {sym}"},
    "what.screener": {"id": "screener perusahaan", "en": "company screener"},

    # --- tool-failure recovery -----------------------------------------------------------
    "recovery.action.not_found": {
        "id": "Tidak mencoba ulang; kode tidak ada di Sectors",
        "en": "Not retried; the code does not exist in Sectors"},
    "recovery.action.malformed": {
        "id": "Tidak mencoba ulang; respons tidak sesuai skema terdokumentasi",
        "en": "Not retried; the response does not match the documented schema"},
    "recovery.action.budget": {
        "id": "Tidak memanggil tool lagi (batas tool call)",
        "en": "No further tool calls (tool-call budget reached)"},
    "recovery.action.retry": {
        "id": "Retry terbatas oleh SectorsService", "en": "Bounded retry by SectorsService"},
    "recovery.outcome.continue": {
        "id": "Dilanjutkan tanpa data ini", "en": "Continued without this data"},
    "gap.tool_failure": {"id": "Data {what} tidak dapat diambil ({status}).",
                         "en": "Could not retrieve {what} ({status})."},

    # --- financial context ----------------------------------------------------------------
    "gap.no_quarterly": {"id": "Tidak ada data kuartalan untuk {sym}.",
                         "en": "No quarterly data for {sym}."},
    "gap.not_applicable": {
        "id": "{label} hanya berlaku untuk emiten perbankan; {sym} ({sub}) dilewati.",
        "en": "{label} applies to banks only; {sym} ({sub}) skipped."},
    "gap.growth_uncomputable": {
        "id": "{label} {sym} tidak dapat dihitung: kuartal pembanding tahun sebelumnya tidak "
              "tersedia.",
        "en": "{label} for {sym} cannot be computed: the prior-year comparison quarter is "
              "unavailable."},
    "gap.metric_missing": {"id": "{label} tidak tersedia di data Sectors untuk {sym}.",
                           "en": "{label} is not available in Sectors data for {sym}."},
    "note.normalized": {"id": "dinormalisasi dari persen ({raw}) ke rasio",
                        "en": "normalised from percent ({raw}) to a ratio"},
    "assumption.normalized": {
        "id": "Rasio {sym} dari company report tercatat dalam satuan persen dan dinormalisasi ke "
              "pecahan sebelum dibandingkan.",
        "en": "{sym} ratios in the company report are expressed in percent and were normalised "
              "to fractions before comparison."},
    "gap.incomplete": {
        "id": "Laporan {sym} {quarter} tidak memuat financials_sector_metrics; metrik terkait "
              "tidak dihitung untuk periode itu.",
        "en": "The {sym} {quarter} report has no financials_sector_metrics; related metrics are "
              "not computed for that period."},
    "note.assumed_latest": {"id": "periode diasumsikan kuartal terakhir yang tersedia",
                            "en": "period assumed to be the latest available quarter"},
    "conflict.detail": {
        "id": "{label} {sym} {quarter}: dihitung {calc} vs laporan {reported}",
        "en": "{label} {sym} {quarter}: calculated {calc} vs reported {reported}"},
    "recovery.conflict.action": {
        "id": "Tidak memilih salah satu nilai; klaim terkait ditahan validator",
        "en": "Neither value chosen; related claims held back by the validator"},
    "recovery.conflict.outcome": {
        "id": "Kedua nilai ditampilkan sebagai kesenjangan data",
        "en": "Both values shown as a data gap"},
    "recovery.requery.action": {
        "id": "Re-query fetch-quarterly-financials dengan report_date",
        "en": "Re-query fetch-quarterly-financials with report_date"},
    "recovery.requery.found": {"id": "Periode ditemukan", "en": "Period found"},
    "recovery.requery.missing": {"id": "Periode tidak tersedia", "en": "Period unavailable"},

    # --- analysis claims -------------------------------------------------------------------
    "claim.value": {"id": "{label} {sym} {period}: {value}", "en": "{label} {sym} {period}: {value}"},
    "claim.growth_inputs": {"id": " ({cur} vs {prev} pada {prev_period})",
                            "en": " ({cur} vs {prev} in {prev_period})"},
    "gap.unavailable_period": {
        "id": "{label} {sym} untuk periode {period} tidak tersedia.",
        "en": "{label} for {sym} in {period} is unavailable."},
    "assumption.common_period": {
        "id": "{label}: dibandingkan pada periode bersama {period}; {ahead} sudah memiliki data "
              "lebih baru.",
        "en": "{label}: compared on the common period {period}; {ahead} already has newer data."},
    "assumption.conflicted_excluded": {
        "id": "{label}: {syms} dikeluarkan dari perbandingan karena nilai antar-sumber "
              "bertentangan.",
        "en": "{label}: {syms} excluded from the comparison because sources disagree."},
    "gap.too_few_peers": {
        "id": "{label}: kurang dari dua emiten dengan data yang dapat dibandingkan.",
        "en": "{label}: fewer than two companies with comparable data."},
    "period.mixed": {"id": "periode berbeda", "en": "mixed periods"},
    "claim.comparison": {
        "id": "{label} ({period}): tertinggi {hi} {hi_v}, terendah {lo} {lo_v}, selisih {range}, "
              "median {median}",
        "en": "{label} ({period}): highest {hi} {hi_v}, lowest {lo} {lo_v}, spread {range}, "
              "median {median}"},
    "claim.comparison_outliers": {"id": "; {syms} menyimpang jauh dari median peer",
                                  "en": "; {syms} far from the peer median"},
    "claim.trend": {"id": "{label} {sym} {p1} vs {p0}: {v1} vs {v0} ({delta})",
                    "en": "{label} {sym} {p1} vs {p0}: {v1} vs {v0} ({delta})"},

    # --- validator ---------------------------------------------------------------------------
    "issue.missing_source": {"id": "Klaim tidak memiliki bukti yang dapat ditelusuri",
                             "en": "The claim has no traceable evidence"},
    "issue.unsupported_metric": {"id": "Metrik {metric} belum didukung agen ini",
                                 "en": "Metric {metric} is not supported by this agent"},
    "issue.wrong_company": {"id": "Bukti {ev} milik {owner}, bukan {claimed}",
                            "en": "Evidence {ev} belongs to {owner}, not {claimed}"},
    "issue.wrong_period_metric": {"id": "Bukti {ev} periode {ev_period}, klaim periode {period}",
                                  "en": "Evidence {ev} is for {ev_period}, the claim for {period}"},
    "issue.wrong_period_calc": {"id": "Bukti {ev} periode {ev_period} di luar {allowed}",
                                "en": "Evidence {ev} period {ev_period} is outside {allowed}"},
    "issue.mixed_periods": {"id": "Perbandingan memakai periode berbeda antar emiten: {periods}",
                            "en": "The comparison mixes periods across companies: {periods}"},
    "issue.min_two": {"id": "Perbandingan butuh minimal dua emiten",
                      "en": "A comparison needs at least two companies"},
    "issue.event_outside": {"id": "Tanggal peristiwa {date} di luar jendela waktu",
                            "en": "Event date {date} is outside the timeframe"},
    "issue.missing_input": {"id": "Input '{name}' untuk perhitungan tidak memiliki bukti bernilai",
                            "en": "Calculation input '{name}' has no evidence with a value"},
    "issue.stale": {"id": "Data periode {period} sudah lama", "en": "Data for {period} is old"},

    # --- second-hop ----------------------------------------------------------------------------
    "hop.why.dividend_capacity": {
        "id": "Agenda dividen: tren laba dan ROE memberi konteks kapasitas pembagian dividen",
        "en": "Dividend event: earnings trend and ROE give context on dividend capacity"},
    "hop.why.governance_decision": {
        "id": "RUPS dapat memutuskan penggunaan laba; kinerja terbaru memberi konteks",
        "en": "The AGM may decide how profit is used; recent performance gives context"},
    "hop.why.ownership_shift": {
        "id": "Perubahan kepemilikan material: konteks kinerja keuangan terbaru",
        "en": "Material ownership change: context from recent financial performance"},
    "hop.why.corporate_action_context": {
        "id": "Aksi korporasi: konteks kinerja membantu membaca peristiwa ini",
        "en": "Corporate action: performance context helps read this event"},
    "hop.skip.threshold": {
        "id": "Skor relevansi {score} di bawah ambang second-hop ({threshold})",
        "en": "Relevance score {score} below the second-hop threshold ({threshold})"},
    "hop.skip.llm": {"id": "LLM menilai konteks keuangan tidak diperlukan",
                     "en": "The LLM judged financial context unnecessary"},
    "hop.reuse": {"id": "Konteks keuangan emiten ini sudah diambil untuk peristiwa lain",
                  "en": "Financial context for this company was already retrieved"},
    "hop.skip.cap": {"id": "Batas second-hop ({cap} emiten) tercapai",
                     "en": "Second-hop limit ({cap} companies) reached"},
    "hop.skip.budget": {"id": "Sisa anggaran tool call tidak cukup",
                        "en": "Not enough tool-call budget left"},
    "hop.budget.action": {"id": "Tidak melakukan riset lanjutan",
                          "en": "No follow-up research"},
    "hop.budget.outcome": {"id": "Dicatat sebagai kesenjangan data", "en": "Recorded as a data gap"},
    "gap.budget_second_hop": {
        "id": "Konteks keuangan {sym} tidak diambil karena batas tool call.",
        "en": "Financial context for {sym} not retrieved because of the tool-call limit."},
    "hop.finding": {"id": "Riset lanjutan {sym}: {reason}", "en": "Follow-up research {sym}: {reason}"},

    # --- resolution & clarification ----------------------------------------------------------
    "trace.entities": {"id": "emiten: {companies}; sektor: {sector}",
                       "en": "companies: {companies}; sector: {sector}"},
    "trace.intent": {"id": "{name} ({source}, {confidence})", "en": "{name} ({source}, {confidence})"},
    "trace.advice": {"id": "dijawab dalam batas riset faktual",
                     "en": "answered within factual research boundaries"},
    "recovery.timeframe.action": {"id": "Memakai jendela default yang terdokumentasi",
                                  "en": "Using the documented default window"},
    "recovery.ambiguous.action": {"id": "Meminta klarifikasi, tidak menebak",
                                  "en": "Asking for clarification instead of guessing"},
    "question.which_company": {"id": "Emiten mana yang Anda maksud? {options}",
                               "en": "Which company do you mean? {options}"},
    "question.option": {"id": "'{text}' → {candidates}", "en": "'{text}' → {candidates}"},
    "word.or": {"id": " atau ", "en": " or "},
    "recovery.unknown.action": {"id": "Diverifikasi ke Sectors (fetch-company-report)",
                                "en": "Verified against Sectors (fetch-company-report)"},
    "recovery.unknown.outcome": {"id": "Tidak ditemukan; dikeluarkan dari cakupan",
                                 "en": "Not found; removed from scope"},
    "gap.unknown_company": {"id": "Kode {sym} tidak ditemukan di Sectors.",
                            "en": "Code {sym} was not found in Sectors."},
    "recovery.unverified.action": {"id": "Verifikasi gagal atau melebihi batas verifikasi",
                                   "en": "Verification failed or exceeded the verification limit"},
    "recovery.unverified.outcome": {"id": "Dikeluarkan dari cakupan; tidak diasumsikan valid",
                                    "en": "Removed from scope; not assumed valid"},
    "gap.unverified_company": {"id": "Kode {sym} tidak dapat diverifikasi.",
                               "en": "Code {sym} could not be verified."},
    "recovery.unsupported.action": {
        "id": "Tidak diestimasi; hanya metrik yang didukung agen yang dipakai",
        "en": "Not estimated; only metrics supported by the agent are used"},
    "recovery.unsupported.outcome": {"id": "Dilaporkan sebagai kesenjangan data",
                                     "en": "Reported as a data gap"},
    "gap.unsupported_metric": {"id": "{label} belum didukung oleh agen ini.",
                               "en": "{label} is not supported by this agent yet."},
    "assumption.substitute_bundle": {
        "id": "Metrik yang diminta tidak tersedia; ditampilkan bundle profitabilitas sebagai konteks "
              "pengganti.",
        "en": "The requested metric is unavailable; the profitability bundle is shown as "
              "substitute context."},
    "question.clarify": {
        "id": "Mohon sebutkan emiten (mis. BBCA), sektor (mis. perbankan), atau jenis analisis yang "
              "Anda inginkan.",
        "en": "Please name a company (e.g. BBCA), a sector (e.g. banking), or the analysis you want."},
    "question.discovery_scope": {
        "id": "Untuk memantau disclosure, sebutkan sektor atau daftar emiten (watchlist).",
        "en": "To monitor disclosures, please name a sector or a list of companies (watchlist)."},
    "question.not_found": {
        "id": "Emiten yang disebut tidak ditemukan. Mohon periksa kode sahamnya.",
        "en": "The companies mentioned were not found. Please check the ticker codes."},
    "clarification.title": {"id": "Klarifikasi diperlukan", "en": "Clarification needed"},
    "gap.unknown_sector": {"id": "Sub-sektor '{slug}' tidak dikenali oleh Sectors.",
                           "en": "Sub-sector '{slug}' is not recognised by Sectors."},
    "gap.sector_members": {"id": "Daftar emiten sub-sektor {slug} tidak dapat diambil.",
                           "en": "Could not retrieve the company list for sub-sector {slug}."},
    "recovery.insufficient.action": {"id": "Tidak menyusun temuan tanpa bukti",
                                     "en": "No findings without evidence"},
    "recovery.insufficient.outcome": {"id": "Kesenjangan data ditampilkan ke pengguna",
                                      "en": "Data gaps shown to the user"},

    # --- trace details --------------------------------------------------------------------------
    "trace.plan_rejected": {"id": " (usulan LLM ditolak: {reason})",
                            "en": " (LLM proposal rejected: {reason})"},
    "trace.empty_scope": {"id": "cakupan kosong", "en": "empty scope"},
    "trace.discovery": {
        "id": "{n} emiten; {events} peristiwa mentah (filing {fs}–{fe}, agenda {s}–{e})",
        "en": "{n} companies; {events} raw events (filings {fs}–{fe}, schedule {s}–{e})"},
    "trace.relevant": {"id": "{n} relevan dari {unique} unik; {dups} duplikat dihapus",
                       "en": "{n} relevant of {unique} unique; {dups} duplicate(s) removed"},
    "trace.no_second_hop": {"id": "tidak ada peristiwa yang membutuhkan riset lanjutan",
                            "en": "no event needs follow-up research"},
    "trace.evidence_count": {"id": "{n} bukti tercatat", "en": "{n} evidence items recorded"},
    "trace.scope": {"id": "{n} emiten dalam cakupan analisis", "en": "{n} companies in analysis scope"},
    "trace.validated": {"id": "{accepted} klaim diterima, {rejected} ditolak; kecukupan bukti: {suff}",
                        "en": "{accepted} claims accepted, {rejected} rejected; evidence: {suff}"},
    "trace.llm_fallback": {"id": "{purpose}: {kind}; aturan deterministik dipakai",
                           "en": "{purpose}: {kind}; deterministic rules used"},
    "trace.llm_ignored": {"id": "{n} id peristiwa di luar kandidat",
                          "en": "{n} event ids outside the candidates"},

    # --- planner step reasons --------------------------------------------------------------------
    "step.discover_events": {
        "id": "Kumpulkan filing dan aksi korporasi dalam cakupan dan jendela waktu",
        "en": "Collect filings and corporate actions in scope and timeframe"},
    "step.rank_relevance": {
        "id": "Normalisasi, deduplikasi, dan nilai relevansi peristiwa dengan aturan deterministik",
        "en": "Normalise, deduplicate and score events with deterministic rules"},
    "step.second_hop_context": {"id": "Ambil konteks keuangan untuk peristiwa yang cukup material",
                                "en": "Retrieve financial context for material events"},
    "step.retrieve_financial_context": {"id": "Ambil data keuangan dan rasio dari Sectors",
                                        "en": "Retrieve financial data and ratios from Sectors"},
    "step.compare_peers": {"id": "Selaraskan periode lalu bandingkan metrik antar emiten",
                           "en": "Align periods, then compare metrics across companies"},
    "step.company_trends": {"id": "Hitung tren kinerja emiten", "en": "Compute company trends"},
    "step.validate_evidence": {"id": "Periksa setiap klaim terhadap bukti",
                               "en": "Check every claim against evidence"},
    "step.synthesize": {"id": "Susun ringkasan faktual dari klaim tervalidasi",
                        "en": "Write a factual summary from validated claims"},

    # --- timeframe -----------------------------------------------------------------------------
    "tf.range": {"id": "{start} s/d {end}", "en": "{start} – {end}"},
    "tf.next_week": {"id": "minggu depan ({start} s/d {end})", "en": "next week ({start} – {end})"},
    "tf.this_week": {"id": "minggu ini ({start} s/d {end})", "en": "this week ({start} – {end})"},
    "tf.last_week": {"id": "minggu lalu ({start} s/d {end})", "en": "last week ({start} – {end})"},
    "tf.next_month": {"id": "bulan depan ({start} s/d {end})", "en": "next month ({start} – {end})"},
    "tf.today": {"id": "hari ini ({day})", "en": "today ({day})"},
    "tf.next_days": {"id": "{n} hari ke depan", "en": "next {n} days"},
    "tf.last_days": {"id": "{n} hari terakhir", "en": "last {n} days"},
    "tf.default_forward": {"id": "{n} hari ke depan (asumsi)", "en": "next {n} days (assumed)"},
    "tf.latest_reports": {"id": "periode laporan terbaru yang tersedia",
                          "en": "latest available reporting period"},
    "tf.default_around": {"id": "30 hari terakhir dan 30 hari ke depan (asumsi)",
                          "en": "last 30 days and next 30 days (assumed)"},
    "tf.note.vague": {"id": "Frasa waktu '{phrase}' tidak spesifik; ",
                      "en": "Time phrase '{phrase}' is not specific; "},
    "tf.note.none": {"id": "Tidak ada jendela waktu; ", "en": "No timeframe given; "},
    "tf.note.forward": {"id": "memakai {n} hari ke depan dan filing {lookback} hari terakhir.",
                        "en": "using the next {n} days and filings from the last {lookback} days."},
    "tf.note.around": {"id": "memakai 30 hari ke belakang dan ke depan.",
                       "en": "using 30 days back and 30 days ahead."},

    # --- briefing --------------------------------------------------------------------------------
    "briefing.boundary": {
        "id": "Informasi faktual untuk riset berbasis data Sectors — bukan rekomendasi beli, jual, "
              "atau tahan.",
        "en": "Factual research information based on Sectors data — not a buy, sell or hold "
              "recommendation."},
    "briefing.advice": {
        "id": "Pertanyaan Anda menyentuh keputusan investasi. Agen ini tidak memberi rekomendasi; "
              "berikut konteks faktual yang dapat Anda pertimbangkan sendiri.",
        "en": "Your question touches on an investment decision. This agent does not give "
              "recommendations; here is factual context for you to weigh yourself."},
    "heading.events": {"id": "Peristiwa yang perlu diperhatikan", "en": "Events worth attention"},
    "heading.second_hop": {"id": "Konteks keuangan (second-hop)",
                           "en": "Financial context (second-hop)"},
    "heading.peer": {"id": "Perbandingan peer", "en": "Peer comparison"},
    "heading.trend": {"id": "Kinerja dan tren", "en": "Performance and trends"},
    "heading.related_events": {"id": "Peristiwa terkait", "en": "Related events"},
    "finding.why_event": {"id": "Relevan karena: {why} (skor {score})",
                          "en": "Relevant because: {why} (score {score})"},
    "summary.discovery": {
        "id": "{n} peristiwa relevan dari {unique} peristiwa unik ({dups} duplikat dihapus) untuk "
              "{scope}, {timeframe}; {selected} peristiwa mendapat riset keuangan lanjutan.",
        "en": "{n} relevant events out of {unique} unique ({dups} duplicate(s) removed) for {scope}, "
              "{timeframe}; {selected} events received follow-up financial research."},
    "summary.peer": {"id": "Perbandingan {syms} untuk {metrics} berdasarkan data Sectors.",
                     "en": "Comparison of {syms} on {metrics} based on Sectors data."},
    "summary.company": {"id": "Konteks keuangan dan peristiwa {syms}.",
                        "en": "Financial context and events for {syms}."},
    "summary.insufficient": {"id": "Bukti tidak cukup untuk menyusun temuan. ",
                             "en": "Not enough evidence to report findings. "},
    "gap.conflict": {"id": "Nilai bertentangan — {detail}.", "en": "Conflicting values — {detail}."},
    "gap.rejected": {"id": "Ditolak: \"{statement}\" — {detail}.",
                     "en": "Rejected: \"{statement}\" — {detail}."},
    "gap.note": {"id": "Catatan: \"{statement}\" — {detail}.",
                 "en": "Note: \"{statement}\" — {detail}."},
}


def t(lang: Language, key: str, **params: object) -> str:
    return MESSAGES[key][lang].format(**params)
