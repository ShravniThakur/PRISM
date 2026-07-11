import { ed25519 } from '@noble/curves/ed25519.js';
import { execSync } from 'child_process';
import fs from 'fs';

function extractSeedFromPKCS8(pem) {
    const base64 = pem.replace(/-----BEGIN PRIVATE KEY-----/, '')
                      .replace(/-----END PRIVATE KEY-----/, '')
                      .replace(/\s+/g, '');
    const der = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    return der.slice(der.length - 32);
}

// Read sebi.pem
const pem = fs.readFileSync('../backend/layer1/app/sebi.pem', 'utf8');
const seed = extractSeedFromPKCS8(pem);

// Message to sign
const messageBytes = new TextEncoder().encode("Hello World");
const sig = ed25519.sign(messageBytes, seed);

console.log("Signature length:", sig.length);
console.log("Signature Base64:", Buffer.from(sig).toString('base64'));
