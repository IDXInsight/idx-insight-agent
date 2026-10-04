/**
 * Landing-page copy in Indonesian and English. Structured (lists of steps, features and
 * glossary terms) rather than flat keys because the page renders these as collections.
 */
import type { Lang } from "./i18n.ts";

type Item = { title: string; text: string };
type Term = { term: string; full: string; meaning: string };

export type LandingCopy = {
  nav: { label: string; journey: string; how: string; glossary: string; open: string; language: string };
  hero: { kicker: string; line1: string; line2: string; text: string; start: string; how: string; trust: [string, string, string] };
  radar: { aria: string; agent: string; caption: string };
  journey: {
    kicker: string; title1: string; title2: string; text: string; viewportAria: string; introAria: string;
    question: string; flowAria: string; adaptive: string; steps: Item[];
  };
  how: { kicker: string; title: string; text: string; features: [Item, Item, Item] };
  principle: { kicker: string; title: string; text: string };
  glossary: { kicker: string; title: string; text: string; sources: string; and: string; terms: Term[] };
  cta: { kicker: string; title: string; text: string; button: string };
  footerStatus: string;
};

export const landingCopy: Record<Lang, LandingCopy> = {
  id: {
    nav: { label: "Navigasi halaman", journey: "Alur riset", how: "Cara kerja", glossary: "Glosarium", open: "Buka ruang riset", language: "Bahasa" },
    hero: {
      kicker: "SECTORS HACKATHON 2026 · IDX BANKING INTELLIGENCE",
      line1: "Temukan konteks.", line2: "Pahami yang penting.",
      text: "IDX Insight adalah agen riset untuk bank tercatat di Bursa Efek Indonesia. Ia membantu memilih disclosure yang relevan, membandingkan metrik antarbank pada periode yang sebanding, lalu menunjukkan bukti di balik setiap temuan.",
      start: "Mulai riset", how: "Lihat cara kerja",
      trust: ["Temuan tervalidasi", "Sumber dapat ditelusuri", "Batas data jelas"],
    },
    radar: {
      aria: "Disclosure, Peer lens, dan Evidence mengorbit pusat IDX Insight dengan gelombang radar",
      agent: "RESEARCH AGENT", caption: "Satu pertanyaan. Beberapa langkah riset. Bukti yang bisa diperiksa.",
    },
    journey: {
      kicker: "01 / ALUR RISET", title1: "Satu pertanyaan.", title2: "Jejak riset yang jelas.",
      text: "Setiap pertanyaan menempuh langkah yang relevan. Geser atau gulir untuk melihat bagaimana jawaban dibangun.",
      viewportAria: "Tahapan alur riset, geser ke samping untuk melihat seluruh langkah",
      introAria: "Contoh pertanyaan riset",
      question: "“Apa yang perlu saya pantau dari bank dalam watchlist minggu ini?”",
      flowAria: "Tujuh tahapan riset", adaptive: "ADAPTIF TERHADAP PERTANYAAN",
      steps: [
        { title: "Mulai dengan pertanyaan", text: "Tanyakan disclosure yang perlu dipantau atau bandingkan kinerja bank dalam watchlist." },
        { title: "Pilih jalur riset", text: "Agen menyesuaikan sumber dan langkah dengan maksud pertanyaan, bukan memanggil semua data sekaligus." },
        { title: "Tentukan cakupan", text: "Emiten, rentang waktu, periode laporan, dan metrik diperiksa sebelum perbandingan dibuat." },
        { title: "Ambil data relevan", text: "Filing, corporate action, atau laporan keuangan diminta dari sumber yang sesuai kebutuhan." },
        { title: "Periksa kesebandingan", text: "Tanggal, satuan, periode, duplikat, dan nilai yang hilang dicek sebelum menjadi temuan." },
        { title: "Susun insight", text: "Jika datanya cukup, agen menyusun briefing dan perbandingan bank yang mudah dibaca." },
        { title: "Telusuri buktinya", text: "Lihat sumber, parameter, waktu data, dan jejak tool di balik klaim yang ditampilkan." },
      ],
    },
    how: {
      kicker: "02 / CARA KERJA", title: "Dari sinyal pasar ke penjelasan yang bisa diuji.",
      text: "Agen memilih langkah berdasarkan pertanyaan. Hasilnya berupa briefing, perbandingan, dan jejak sumber; bukan sekadar daftar data.",
      features: [
        { title: "Disclosure radar", text: "Menelusuri filing dan corporate action yang relevan dengan emiten dan rentang waktu yang diminta. Tanggal mendatang hanya muncul jika ada data pendukung." },
        { title: "Peer lens", text: "Membandingkan bank dengan metrik dan periode yang sebanding. Kesenjangan data serta definisi metrik dinyatakan terbuka." },
        { title: "Evidence trail", text: "Setiap klaim yang diterima memiliki bukti, sumber, periode, dan jejak pemanggilan tool. Data yang tidak cukup tidak diubah menjadi kepastian." },
      ],
    },
    principle: {
      kicker: "PRINSIP DATA", title: "Ketika data terbatas, kami mengatakannya.",
      text: "Data pasar utama Sectors bersifat akhir hari perdagangan (EOD), bukan real-time. Angka dan kejadian hanya ditampilkan dari respons backend. Jika sumber atau periode tidak memadai, ruang riset menunjukkan celah data alih-alih mengarang grafik.",
    },
    glossary: {
      kicker: "03 / GLOSARIUM", title: "Kenali istilah sebelum membaca angka.",
      text: "Definisi ringkas untuk membantu membaca riset bank. Interpretasi akhir tetap bergantung pada definisi dan periode setiap sumber data.",
      sources: "Rujukan definisi:", and: "dan",
      terms: [
        { term: "ROE", full: "Return on Equity", meaning: "Mengukur laba terhadap ekuitas pemegang saham. Membantu melihat imbal hasil atas modal bank." },
        { term: "ROA", full: "Return on Assets", meaning: "Mengukur laba terhadap total aset. Membantu melihat kemampuan aset bank menghasilkan laba." },
        { term: "NIM", full: "Net Interest Margin", meaning: "Membandingkan pendapatan bunga bersih dengan rata-rata aset produktif. Memberi konteks margin bisnis bunga bank." },
        { term: "BOPO", full: "Biaya Operasional / Pendapatan Operasional", meaning: "Rasio biaya operasional terhadap pendapatan operasional. Angka lebih rendah umumnya menandakan efisiensi lebih baik. Metrik ini belum didukung oleh backend saat ini." },
        { term: "Cost-to-income", full: "Rasio biaya terhadap pendapatan", meaning: "Membandingkan beban dan pendapatan menurut definisi data yang tersedia. Jangan langsung menyamakannya dengan BOPO tanpa memeriksa komponen perhitungannya." },
        { term: "NPL", full: "Non-Performing Loan", meaning: "Rasio kredit bermasalah terhadap total kredit. Membantu membaca kualitas kredit." },
        { term: "LDR", full: "Loan to Deposit Ratio", meaning: "Membandingkan kredit yang disalurkan dengan dana pihak ketiga. Memberi gambaran penyaluran dana dan likuiditas." },
        { term: "CAR", full: "Capital Adequacy Ratio", meaning: "Membandingkan modal bank dengan aset tertimbang menurut risiko. Membantu membaca kecukupan modal." },
        { term: "CASA", full: "Current Account Savings Account", meaning: "Porsi giro dan tabungan dalam dana pihak ketiga; sering dipakai untuk melihat komposisi dana murah." },
        { term: "YoY", full: "Year over Year", meaning: "Perbandingan dengan periode yang sama satu tahun sebelumnya, misalnya laba kuartal ini dibanding kuartal yang sama tahun lalu." },
      ],
    },
    cta: {
      kicker: "MULAI DARI PERTANYAAN", title: "Apa yang perlu Anda pahami hari ini?",
      text: "Tanyakan disclosure bank dalam watchlist atau bandingkan kinerja beberapa emiten. Hasil akan mengikuti data yang tersedia pada backend.",
      button: "Buka ruang riset",
    },
    footerStatus: "Tentang proyek",
  },
  en: {
    nav: { label: "Page navigation", journey: "Research flow", how: "How it works", glossary: "Glossary", open: "Open the workspace", language: "Language" },
    hero: {
      kicker: "SECTORS HACKATHON 2026 · IDX BANKING INTELLIGENCE",
      line1: "Find the context.", line2: "Understand what matters.",
      text: "IDX Insight is a research agent for banks listed on the Indonesia Stock Exchange. It helps pick the disclosures that matter, compares metrics across banks over comparable periods, and shows the evidence behind every finding.",
      start: "Start researching", how: "See how it works",
      trust: ["Validated findings", "Traceable sources", "Clear data limits"],
    },
    radar: {
      aria: "Disclosure, Peer lens and Evidence orbit the IDX Insight core with radar waves",
      agent: "RESEARCH AGENT", caption: "One question. Several research steps. Evidence you can check.",
    },
    journey: {
      kicker: "01 / RESEARCH FLOW", title1: "One question.", title2: "A clear research trail.",
      text: "Every question takes only the steps it needs. Swipe or scroll to see how an answer is built.",
      viewportAria: "Research flow stages, swipe sideways to see every step",
      introAria: "Example research question",
      question: "“What should I watch for the banks on my watchlist this week?”",
      flowAria: "Seven research stages", adaptive: "ADAPTS TO THE QUESTION",
      steps: [
        { title: "Start with a question", text: "Ask which disclosures to watch, or compare the performance of banks on your watchlist." },
        { title: "Choose a research path", text: "The agent fits its sources and steps to what you asked instead of fetching everything at once." },
        { title: "Set the scope", text: "Companies, time window, reporting period and metrics are checked before any comparison." },
        { title: "Fetch relevant data", text: "Filings, corporate actions or financial reports are requested from the source that fits." },
        { title: "Check comparability", text: "Dates, units, periods, duplicates and missing values are checked before anything becomes a finding." },
        { title: "Build the insight", text: "When the data is sufficient, the agent writes a readable briefing and bank comparison." },
        { title: "Trace the evidence", text: "See the source, parameters, data time and tool trail behind every claim shown." },
      ],
    },
    how: {
      kicker: "02 / HOW IT WORKS", title: "From market signals to explanations you can test.",
      text: "The agent chooses its steps from your question. The result is a briefing, a comparison and a source trail, not just a list of data.",
      features: [
        { title: "Disclosure radar", text: "Finds the filings and corporate actions relevant to the companies and time window you ask about. Future dates appear only when data supports them." },
        { title: "Peer lens", text: "Compares banks on comparable metrics and periods. Data gaps and metric definitions are stated openly." },
        { title: "Evidence trail", text: "Every accepted claim carries its evidence, source, period and tool-call trail. Insufficient data is never turned into certainty." },
      ],
    },
    principle: {
      kicker: "DATA PRINCIPLE", title: "When data is limited, we say so.",
      text: "Sectors' core market data is end of day (EOD), not real time. Figures and events are shown only from the backend's responses. When a source or period is not good enough, the workspace shows the data gap instead of inventing a chart.",
    },
    glossary: {
      kicker: "03 / GLOSSARY", title: "Know the terms before reading the numbers.",
      text: "Short definitions to help read bank research. The final reading still depends on each data source's definition and period.",
      sources: "Definition references:", and: "and",
      terms: [
        { term: "ROE", full: "Return on Equity", meaning: "Profit relative to shareholders' equity. Shows the return on the bank's capital." },
        { term: "ROA", full: "Return on Assets", meaning: "Profit relative to total assets. Shows how well the bank's assets generate profit." },
        { term: "NIM", full: "Net Interest Margin", meaning: "Net interest income relative to average earning assets. Gives context on the margin of the lending business." },
        { term: "BOPO", full: "Operating Expenses / Operating Income", meaning: "Operating expenses relative to operating income. A lower figure usually means better efficiency. The backend does not support this metric yet." },
        { term: "Cost-to-income", full: "Cost-to-income ratio", meaning: "Compares costs with income under the definition of the data available. Do not treat it as BOPO without checking how it is calculated." },
        { term: "NPL", full: "Non-Performing Loan", meaning: "Non-performing loans relative to total loans. Helps read credit quality." },
        { term: "LDR", full: "Loan to Deposit Ratio", meaning: "Loans extended relative to third-party funds. Gives a picture of lending and liquidity." },
        { term: "CAR", full: "Capital Adequacy Ratio", meaning: "Bank capital relative to risk-weighted assets. Helps read capital adequacy." },
        { term: "CASA", full: "Current Account Savings Account", meaning: "The share of current and savings accounts in third-party funds; often used to read the mix of low-cost funding." },
        { term: "YoY", full: "Year over Year", meaning: "A comparison with the same period one year earlier, e.g. this quarter's profit against the same quarter last year." },
      ],
    },
    cta: {
      kicker: "START WITH A QUESTION", title: "What do you need to understand today?",
      text: "Ask about disclosures for the banks on your watchlist, or compare the performance of several companies. Results follow the data available in the backend.",
      button: "Open the workspace",
    },
    footerStatus: "About the project",
  },
};
