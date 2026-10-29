// Smoke-test the research/web/video tooling. Run: node scripts/check-tooling.mjs
import 'dotenv/config';
import { execSync } from 'node:child_process';

const ok = (m) => console.log(`  OK   ${m}`);
const bad = (m) => console.log(`  FAIL ${m}`);

// Playwright — no key needed
try {
  const { chromium } = await import('playwright');
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent('<title>fbf</title>');
  (await p.title()) === 'fbf' ? ok('Playwright + Chromium') : bad('Playwright title mismatch');
  await b.close();
} catch (e) { bad(`Playwright: ${e.message.split('\n')[0]} (run: npx playwright install chromium)`); }

// HyperFrames — CLI + ffmpeg
try { ok(`HyperFrames CLI ${execSync('npx hyperframes --version').toString().trim()}`); } catch { bad('HyperFrames CLI'); }
try { execSync('ffmpeg -version', { stdio: 'ignore' }); ok('ffmpeg on PATH'); } catch { bad('ffmpeg not on PATH (needed by HyperFrames render)'); }

// Perplexity
if (!process.env.PERPLEXITY_API_KEY || process.env.PERPLEXITY_API_KEY.includes('your_key')) bad('PERPLEXITY_API_KEY not set in .env');
else try {
  const { default: Perplexity } = await import('@perplexity-ai/perplexity_ai');
  const r = await new Perplexity().chat.completions.create({ model: 'sonar', messages: [{ role: 'user', content: 'Reply with OK' }] });
  ok(`Perplexity: ${r.choices[0].message.content.slice(0, 40)}`);
} catch (e) { bad(`Perplexity: ${e.message}`); }

// Firecrawl
if (!process.env.FIRECRAWL_API_KEY || process.env.FIRECRAWL_API_KEY.includes('your_key')) bad('FIRECRAWL_API_KEY not set in .env');
else try {
  const { default: Firecrawl } = await import('firecrawl');
  const doc = await new Firecrawl({ apiKey: process.env.FIRECRAWL_API_KEY }).scrape('https://example.com', { formats: ['markdown'] });
  ok(`Firecrawl scrape: ${(doc.markdown || '').slice(0, 30).replace(/\n/g, ' ')}`);
} catch (e) { bad(`Firecrawl: ${e.message}`); }
