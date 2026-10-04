"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, ArrowRight, ArrowUpRight, BarChart3, BookOpen, CalendarDays, CheckCircle2, Database, FileSearch, ShieldCheck } from "lucide-react";
import AnimatedWaveFooter from "@/components/ui/animated-wave-footer";
import Timeline from "@/components/ui/timeline";
import { ShaderBackground } from "@/components/ui/shader-background";
import HeroRadar from "@/components/hero-radar";
import { FlipLink } from "@/components/ui/flip-button";

const glossary = [
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
];

export default function Home() {
  const router = useRouter();
  return <div className="site-page">
    <header className="site-header"><Link href="/" className="site-brand"><span><Activity size={21} /></span>idx<em>insight</em></Link><nav aria-label="Navigasi utama"><a href="#journey">Cara kerja</a><a href="#glosarium">Glosarium</a><FlipLink href="/research" className="header-action" label="Buka ruang riset" icon={<ArrowUpRight size={15} />} /></nav></header>
    <main className="landing-main">
      <section className="hero"><ShaderBackground className="hero-shader" /><div className="hero-copy"><span className="kicker"><span /> SECTORS HACKATHON 2026 · IDX BANKING INTELLIGENCE</span><h1>Temukan konteks.<br /><strong>Pahami yang penting.</strong></h1><p>IDX Insight adalah agen riset untuk bank tercatat di Bursa Efek Indonesia. Ia membantu memilih disclosure yang relevan, membandingkan metrik antarbank pada periode yang sebanding, lalu menunjukkan bukti di balik setiap temuan.</p><div className="hero-actions"><FlipLink href="/research" className="cta-primary" label="Mulai riset" icon={<ArrowRight size={17} />} /><FlipLink href="#journey" className="cta-secondary" label="Lihat cara kerja" icon={<ArrowUpRight size={16} />} /></div><div className="hero-trust"><span><ShieldCheck size={16} /> Temuan tervalidasi</span><span><Database size={16} /> Sumber dapat ditelusuri</span><span><CheckCircle2 size={16} /> Batas data jelas</span></div></div><HeroRadar /></section>
      <Timeline />
      <section className="landing-section" id="cara-kerja"><div className="section-lead"><span className="kicker">01 / CARA KERJA</span><h2>Dari sinyal pasar ke penjelasan yang bisa diuji.</h2><p>Agen memilih langkah berdasarkan pertanyaan. Hasilnya berupa briefing, perbandingan, dan jejak sumber; bukan sekadar daftar data.</p></div><div className="feature-grid"><article><span className="feature-icon"><CalendarDays size={23} /></span><span className="feature-number">01</span><h3>Disclosure radar</h3><p>Menelusuri filing dan corporate action yang relevan dengan emiten dan rentang waktu yang diminta. Tanggal mendatang hanya muncul jika ada data pendukung.</p></article><article><span className="feature-icon"><BarChart3 size={23} /></span><span className="feature-number">02</span><h3>Peer lens</h3><p>Membandingkan bank dengan metrik dan periode yang sebanding. Kesenjangan data serta definisi metrik dinyatakan terbuka.</p></article><article><span className="feature-icon"><FileSearch size={23} /></span><span className="feature-number">03</span><h3>Evidence trail</h3><p>Setiap klaim yang diterima memiliki bukti, sumber, periode, dan jejak pemanggilan tool. Data yang tidak cukup tidak diubah menjadi kepastian.</p></article></div></section>
      <section className="principle-band"><div><span className="kicker">PRINSIP DATA</span><h2>Ketika data terbatas, kami mengatakannya.</h2></div><p>Data pasar utama Sectors bersifat akhir hari perdagangan (EOD), bukan real-time. Angka dan kejadian hanya ditampilkan dari respons backend. Jika sumber atau periode tidak memadai, ruang riset menunjukkan celah data alih-alih mengarang grafik.</p></section>
      <section className="landing-section glossary-section" id="glosarium"><div className="section-lead"><span className="kicker">02 / GLOSARIUM</span><h2>Kenali istilah sebelum membaca angka.</h2><p>Definisi ringkas untuk membantu membaca riset bank. Interpretasi akhir tetap bergantung pada definisi dan periode setiap sumber data.</p></div><div className="glossary-grid">{glossary.map(item => <article key={item.term} className="glossary-card"><div><span className="glossary-term">{item.term}</span><BookOpen size={17} /></div><h3>{item.full}</h3><p>{item.meaning}</p></article>)}</div><p className="glossary-sources">Rujukan definisi: <a href="https://www.bi.go.id/id/statistik/Metadata/SSKI/Documents/02_Indikator_Sektor_Perbankan.pdf" target="_blank" rel="noopener noreferrer">Bank Indonesia <ArrowUpRight size={12} /></a> dan <a href="https://www.wip.ojk.go.id/id/regulasi/Documents/Pages/Transparansi-dan-Publikasi-Laporan-Bank-Umum-Konvensional/seojk%209-2020.pdf" target="_blank" rel="noopener noreferrer">OJK <ArrowUpRight size={12} /></a>.</p></section>
      <section className="landing-cta"><div><span className="kicker">MULAI DARI PERTANYAAN</span><h2>Apa yang perlu Anda pahami hari ini?</h2><p>Tanyakan disclosure bank dalam watchlist atau bandingkan kinerja beberapa emiten. Hasil akan mengikuti data yang tersedia pada backend.</p></div><FlipLink href="/research" className="cta-primary" label="Buka ruang riset" icon={<ArrowRight size={18} />} /></section>
    </main><AnimatedWaveFooter activeView="home" lang="id" statusLabel="Tentang proyek"
      onNavigate={view => router.push(`/research?view=${view}`)}
      onNewResearch={() => router.push("/research")}
      onOpenGuide={() => document.getElementById("journey")?.scrollIntoView({ behavior: "smooth" })}
      onOpenTrace={() => document.getElementById("journey")?.scrollIntoView({ behavior: "smooth" })} />
  </div>;
}
