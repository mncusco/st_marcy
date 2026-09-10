// /api/subscribe.js
// Vercel Serverless Function — soluzione INDIPENDENTE (non collegata a ST CORE)
// per il libro "La Montagna Che Portiamo Dentro".
//
// Riceve l'email dal form sul sito, la salva su Neon Postgres,
// e restituisce il link di download del PDF.
//
// SETUP RICHIESTO (una tantum):
// 1. Su Vercel → Project (st_marcy) → Settings → Environment Variables:
//      MONTAGNA_DATABASE_URL = <la connection string Neon>
//    (nome diverso da eventuali variabili già usate da ST CORE, per non
//    creare conflitti con l'altro sistema)
//
// 2. Nel SQL Editor di Neon (console.neon.tech → il tuo progetto → SQL Editor),
//    esegui una sola volta:
//
//    CREATE TABLE IF NOT EXISTS montagna_subscribers (
//      id SERIAL PRIMARY KEY,
//      email TEXT NOT NULL UNIQUE,
//      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
//    );
//
// 3. Metti il PDF reale del libro in:
//    /la-montagna-che-portiamo-dentro/downloads/la-montagna-che-portiamo-dentro.pdf
//
// 4. Assicurati che "pg" sia nelle dependencies del package.json alla radice del repo.

const { Pool } = require('pg');

let pool;
function getPool() {
  if (!pool) {
    if (!process.env.MONTAGNA_DATABASE_URL) {
      throw new Error('MONTAGNA_DATABASE_URL non configurata');
    }
    pool = new Pool({
      connectionString: process.env.MONTAGNA_DATABASE_URL,
      ssl: { rejectUnauthorized: false },
    });
  }
  return pool;
}

const BOOK_DOWNLOAD_URL = '/la-montagna-che-portiamo-dentro/downloads/la-montagna-che-portiamo-dentro.pdf';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'method-not-allowed' });
  }

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  const email = (body && body.email || '').trim().toLowerCase();

  if (!email || !EMAIL_RE.test(email)) {
    return res.status(400).json({ error: 'invalid-email' });
  }

  try {
    const db = getPool();
    await db.query(
      `INSERT INTO montagna_subscribers (email) VALUES ($1)
       ON CONFLICT (email) DO NOTHING`,
      [email]
    );

    return res.status(200).json({
      ok: true,
      downloadUrl: BOOK_DOWNLOAD_URL,
    });
  } catch (err) {
    console.error('montagna subscribe error:', err.message);
    return res.status(500).json({ error: 'server-error' });
  }
};
