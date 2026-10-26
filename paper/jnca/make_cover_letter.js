// Cover letter for the JNCA submission. Run: node make_cover_letter.js
// Writes submission/CRSHE_JNCA_cover_letter.docx (A4, Times New Roman 11 pt).
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

const TITLE = "Collusion-resilient, tamper-evident range analytics over homomorphically " +
  "encrypted Internet of Things data in multi-cloud storage";

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
      line("26 October 2026"),
      gap(),
      line("The Editor-in-Chief"),
      line("Journal of Network and Computer Applications"),
      line("Elsevier"),
      gap(),
      p("Subject: Submission of an original research article", { run: { bold: true } }),
      p("Dear Editor-in-Chief,", { align: AlignmentType.LEFT }),
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED, spacing: { after: 120 },
        children: [
          new TextRun("On behalf of my co-authors, I am pleased to submit our manuscript entitled “"),
          new TextRun({ text: TITLE, italics: true }),
          new TextRun("” for consideration as a research article in the "),
          new TextRun({ text: "Journal of Network and Computer Applications", italics: true }),
          new TextRun("."),
        ],
      }),
      p("Internet of Things (IoT) data are increasingly stored encrypted and replicated across " +
        "several cloud providers, while analysts need aggregates over ranges of time, place and " +
        "sensor value. Existing privacy-preserving designs either reveal which records an aggregate " +
        "touches once the clouds compute over them, operate on plaintext data, require an honest " +
        "majority with server-to-server interaction, or cannot cheaply detect tampered answers when " +
        "all but one cloud collude. Our manuscript presents CR-SHE (Collusion-Resilient Searchable " +
        "Homomorphic Encryption), which combines distributed point functions with lattice-based " +
        "homomorphic encryption so that each cloud contracts its share of a hidden selection against " +
        "owner-encrypted data and returns a single ciphertext."),
      p("The main contributions of the manuscript are:", { after: 80 }),
      bullet("One-round oblivious range aggregation over encrypted summed-area tables, in which any " +
        "d-dimensional box becomes 2^{d} padded point keys and the cost depends neither on the range " +
        "nor on the number of records."),
      bullet("Tamper evidence from a secret scalar drawn for each query and carried inside the keys, " +
        "which bounds the probability of accepting a wrong answer by about 2^{−36} without stored " +
        "keys or extra homomorphic work."),
      bullet("Role-scoped access that confines each user to its own role’s records without any " +
        "interaction between cloud providers."),
      bullet("Security proofs against n−1 colluding clouds, together with a C++ prototype and an " +
        "OpenFHE-based implementation evaluated on two real IoT datasets with 825,554 records."),
      p("On these datasets a verified range query costs 0.68–1.19 s per cloud and returns one " +
        "132 kB ciphertext whatever the length of the range, while uploading about 5.5 kB instead of " +
        "the 44 MB that a single-server encrypted query would need. No tampered answer was accepted " +
        "in 4,500 trials, and a frequency attack on the masked index was reduced to random guessing, " +
        "whereas power-of-two padding still leaked."),
      p("We believe the work fits the journal’s scope in cloud computing, the Internet of Things " +
        "and network security applications, and will interest readers who design privacy-preserving " +
        "multi-cloud data services."),
      p("We confirm that the manuscript is original, has not been published previously and is not " +
        "under consideration for publication elsewhere, and that all authors have approved its " +
        "submission. The authors have no competing interests to declare. The use of generative AI " +
        "tools in preparing the manuscript is disclosed in the declaration placed before the " +
        "references. Full proofs and additional experiments are provided as Supplementary Material, " +
        "and both datasets used in the evaluation are publicly available."),
      p("Thank you for considering our manuscript. We look forward to hearing from you."),
      line("Sincerely,"),
      gap(),
      line("Md Mazharul Islam", { bold: true }),
      line("Corresponding author, on behalf of co-authors Mubasshir Ahmed and Md Redowan Zaman Anik"),
    ],
  }],
});

const out = path.join(__dirname, "submission", "CRSHE_JNCA_cover_letter.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out); });
