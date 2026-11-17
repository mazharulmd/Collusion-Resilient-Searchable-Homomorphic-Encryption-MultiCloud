// Cover letter for the IEEE Transactions on Cloud Computing submission. Run: node make_cover_letter.js
// Writes submission/TCC_cover_letter.docx (A4, Times New Roman 11 pt).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat,
} = require("docx");

const FONT = "Times New Roman";
const SIZE = 22; // half-points: 11 pt

// text with ^{...} superscripts, e.g. "2^{d}"
function runs(text, opts = {}) {
  const out = [];
  const re = /\^\{([^}]*)\}/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...opts }));
    out.push(new TextRun({ text: m[1], superScript: true, ...opts }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...opts }));
  return out;
}

const p = (text, extra = {}) =>
  new Paragraph({ children: runs(text, extra.run || {}), spacing: { after: extra.after ?? 120 },
    alignment: extra.align || AlignmentType.JUSTIFIED });
const line = (text, opts = {}) =>
  new Paragraph({ children: runs(text, opts), spacing: { after: 0 } });
const bullet = (text) =>
  new Paragraph({ children: runs(text), numbering: { reference: "bullets", level: 0 },
    spacing: { after: 40 }, alignment: AlignmentType.JUSTIFIED });
const gap = () => new Paragraph({ children: [], spacing: { after: 60 } });

const TITLE = "One-Round Verifiable Range Aggregation over Encrypted Data Replicated " +
  "across Non-Colluding Clouds";

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 567, hanging: 283 } } } }],
    }],
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 },
        margin: { top: 1021, bottom: 1021, left: 1304, right: 1304 } },
    },
    children: [
      line("Md Mazharul Islam", { bold: true }),
      line("Department of Electrical and Computer Engineering"),
      line("North South University"),
      line("Plot 15, Block B, Bashundhara R/A, Dhaka 1229, Bangladesh"),
      line("mazharul.islam1@northsouth.edu"),
      gap(),
      line("17 November 2026"),
      gap(),
      line("The Editor-in-Chief"),
      line("IEEE Transactions on Cloud Computing"),
      gap(),
      p("Subject: Submission of a regular paper", { run: { bold: true } }),
      p("Dear Editor-in-Chief,", { align: AlignmentType.LEFT }),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, spacing: { after: 120 },
        children: [
          new TextRun("On behalf of my co-authors, I submit our manuscript entitled “"),
          new TextRun({ text: TITLE, italics: true }),
          new TextRun("” for consideration as a regular paper in the "),
          new TextRun({ text: "IEEE Transactions on Cloud Computing", italics: true }),
          new TextRun("."),
        ],
      }),
      p("Many organisations keep sensor data encrypted at several cloud providers, while analysts " +
        "need sums and counts over ranges of time, place and value. The paper shows how to answer such " +
        "range queries in one round over data that the owner encrypts once and copies to n clouds. " +
        "Any n−1 colluding clouds learn neither the range, the matching records, their number nor the " +
        "result, and the clouds never communicate with each other."),
      p("The main contributions are:", { after: 80 }),
      bullet("A one-round protocol that answers any d-dimensional box from 2^{d} keys per cloud over " +
        "encrypted summed-area tables, at a cost independent of the range and of the number of records."),
      bullet("A per-query check carried inside the keys, which detects a wrong answer from up to n−1 " +
        "colluding clouds without extra homomorphic work. We also show why the same check fails " +
        "against a single server."),
      bullet("Security proofs and an evaluation on two public IoT datasets, with two alternatives " +
        "measured on the same machine."),
      p("A checked range query took 0.68–1.19 s per cloud on one thread, whatever the length of the " +
        "range, and needed about 5 kB of keys per cloud. A single server holding the same table needed " +
        "a 44 MB encrypted query and could not use the check. No tampered answer was accepted in 1,500 " +
        "trials."),
      p("We believe the paper fits the journal’s scope in security and privacy for cloud storage and " +
        "multi-cloud computing."),
      p("The manuscript is original and is not under consideration elsewhere. All authors have approved the submission and declare no " +
        "competing interests. The use of AI tools is disclosed in the Acknowledgments. Full proofs are " +
        "provided as supplemental material."),
      p("Thank you for considering our manuscript."),
      line("Sincerely,"),
      gap(),
      line("Md Mazharul Islam", { bold: true }),
      line("Corresponding author, on behalf of co-authors Mubasshir Ahmed and Md Redowan Zaman Anik"),
    ],
  }],
});

const out = path.join(__dirname, "submission", "TCC_cover_letter.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out); });
