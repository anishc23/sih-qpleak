"""
Build the two SecureLock PDFs.

    python docs/build_docs.py

Produces docs/SecureLock_Explained.pdf and docs/SecureLock_User_Manual.pdf.
Requires reportlab (pip install reportlab); nothing else, and no network.

The documents are generated rather than hand-written so they can be corrected
and rebuilt when the system changes.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    NextPageTemplate,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent

# The custody-register palette, same values the web app uses.
INK = colors.HexColor("#171B16")
INK3 = colors.HexColor("#454B41")
INK5 = colors.HexColor("#5C6257")
LAC = colors.HexColor("#8E3020")
VERDIGRIS = colors.HexColor("#2E5C4E")
RULE = colors.HexColor("#BEC4B0")
RULE_SOFT = colors.HexColor("#CCD2BF")
REGISTER = colors.HexColor("#E3E7DB")
LEAF = colors.HexColor("#EDF0E5")

PAGE_W, PAGE_H = A4
MARGIN = 22 * mm


# ----------------------------------------------------------------- styles
_base = getSampleStyleSheet()

S = {
    "title": ParagraphStyle(
        "title", parent=_base["Title"], fontName="Times-Bold", fontSize=30,
        leading=34, textColor=INK, alignment=TA_LEFT, spaceAfter=0),
    "subtitle": ParagraphStyle(
        "subtitle", parent=_base["Normal"], fontName="Helvetica", fontSize=12.5,
        leading=18, textColor=INK3, spaceBefore=10),
    "h1": ParagraphStyle(
        "h1", parent=_base["Heading1"], fontName="Times-Bold", fontSize=19,
        leading=23, textColor=INK, spaceBefore=20, spaceAfter=9),
    "h2": ParagraphStyle(
        "h2", parent=_base["Heading2"], fontName="Times-Bold", fontSize=14,
        leading=18, textColor=INK, spaceBefore=15, spaceAfter=6),
    "h3": ParagraphStyle(
        "h3", parent=_base["Heading3"], fontName="Helvetica-Bold", fontSize=10,
        leading=14, textColor=LAC, spaceBefore=12, spaceAfter=4),
    "body": ParagraphStyle(
        "body", parent=_base["Normal"], fontName="Helvetica", fontSize=10,
        leading=15.5, textColor=INK, spaceAfter=8),
    "small": ParagraphStyle(
        "small", parent=_base["Normal"], fontName="Helvetica", fontSize=8.8,
        leading=13, textColor=INK5, spaceAfter=6),
    "quote": ParagraphStyle(
        "quote", parent=_base["Normal"], fontName="Times-Italic", fontSize=12,
        leading=17, textColor=INK3, leftIndent=12, spaceBefore=6, spaceAfter=10),
    "mono": ParagraphStyle(
        "mono", parent=_base["Normal"], fontName="Courier", fontSize=8.6,
        leading=12.5, textColor=INK, spaceAfter=6),
    "cell": ParagraphStyle(
        "cell", parent=_base["Normal"], fontName="Helvetica", fontSize=9,
        leading=13, textColor=INK),
    "cellb": ParagraphStyle(
        "cellb", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=9,
        leading=13, textColor=INK),
    "cellm": ParagraphStyle(
        "cellm", parent=_base["Normal"], fontName="Courier", fontSize=8.4,
        leading=12, textColor=INK),
    "sealbig": ParagraphStyle(
        "sealbig", parent=_base["Normal"], fontName="Times-Bold", fontSize=17,
        leading=21, textColor=REGISTER),
    "pre": ParagraphStyle(
        "pre", parent=_base["Normal"], fontName="Courier", fontSize=8.2,
        leading=11.4, textColor=INK),
    "sealsmall": ParagraphStyle(
        "sealsmall", parent=_base["Normal"], fontName="Courier", fontSize=8.4,
        leading=13, textColor=colors.HexColor("#AFB6A6")),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def H(text, level=1):
    # Deliberately not escaped: headings carry entities such as &mdash;, and
    # every heading in this file is authored here rather than user input.
    return Paragraph(text, S[f"h{level}"])


def bullets(items, style="body"):
    return ListFlowable(
        [ListItem(P(i, style), leftIndent=14, value="circle") for i in items],
        bulletType="bullet", start="circle", leftIndent=14,
        bulletFontSize=5, bulletOffsetY=-2, spaceAfter=8,
    )


def numbered(items, style="body"):
    return ListFlowable(
        [ListItem(P(i, style), leftIndent=16) for i in items],
        bulletType="1", leftIndent=16, spaceAfter=8,
    )


def table(rows, widths, header=True, mono_cols=()):
    """A ruled register table."""
    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if r_i == 0 and header:
                st = "cellb"
            elif c_i in mono_cols:
                st = "cellm"
            else:
                st = "cell"
            out.append(Paragraph(cell, S[st]) if isinstance(cell, str) else cell)
        data.append(out)

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE_SOFT),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), LEAF),
            ("LINEBELOW", (0, 0), (-1, 0), 0.9, RULE),
        ]
    t.setStyle(TableStyle(style))
    t.spaceAfter = 10
    return t


def callout(title, body, tone=LAC):
    """A marginal note, marked in the margin the way a clerk marks one."""
    inner = [Paragraph(f"<b>{title}</b>", S["cellb"]), Spacer(1, 3),
             Paragraph(body, S["cell"])]
    t = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LEAF),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, tone),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
    ]))
    t.spaceAfter = 12
    t.spaceBefore = 6
    return t


def seal_block(lines):
    """The dark object, reproduced on paper."""
    flow = []
    for i, (text, style) in enumerate(lines):
        flow.append(Paragraph(text, S[style]))
        if i != len(lines) - 1:
            flow.append(Spacer(1, 4))
    t = Table([[flow]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
    ]))
    t.spaceAfter = 14
    t.spaceBefore = 6
    return t


def diagram(lines):
    """ASCII art. Preformatted, because Paragraph collapses leading spaces
    and turns an aligned diagram into a paragraph of noise."""
    t = Table([[Preformatted("\n".join(lines), S["pre"])]],
              colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LEAF),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
    ]))
    t.spaceAfter = 12
    return t


def code(lines):
    # Preformatted, not Paragraph: commands must not reflow, and aligned
    # trailing comments must stay aligned.
    t = Table([[Preformatted("\n".join(lines), S["pre"])]],
              colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LEAF),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
    ]))
    t.spaceAfter = 11
    return t


# ----------------------------------------------------------------- template
class Doc(BaseDocTemplate):
    def __init__(self, path, title, running):
        super().__init__(
            str(path), pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=MARGIN + 6 * mm,
            title=title, author="SecureLock", subject=running,
        )
        self.running = running
        frame = Frame(MARGIN, MARGIN + 6 * mm, PAGE_W - 2 * MARGIN,
                      PAGE_H - 2 * MARGIN - 6 * mm, id="body")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._cover_bg),
            PageTemplate(id="body", frames=[frame], onPage=self._chrome),
        ])

    def _cover_bg(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(REGISTER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    def _chrome(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(REGISTER)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - MARGIN + 5 * mm,
                    PAGE_W - MARGIN, PAGE_H - MARGIN + 5 * mm)
        canvas.setFont("Courier", 7.5)
        canvas.setFillColor(INK5)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 7.5 * mm, self.running.upper())
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 7.5 * mm, "SECURELOCK")

        canvas.line(MARGIN, MARGIN + 2 * mm, PAGE_W - MARGIN, MARGIN + 2 * mm)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 2.5 * mm, str(doc.page))
        canvas.drawString(MARGIN, MARGIN - 2.5 * mm,
                          "SIH internal prototype - runs offline")
        canvas.restoreState()


# ================================================================ DOCUMENT 1
def build_explained():
    doc = Doc(OUT / "SecureLock_Explained.pdf",
              "SecureLock - Explained From Scratch", "Explained from scratch")
    f = []

    # ------------------------------------------------------------- cover
    f += [
        Spacer(1, 30 * mm),
        Paragraph("SecureLock", S["title"]),
        Paragraph("How it works, explained from scratch", S["subtitle"]),
        Spacer(1, 12 * mm),
        seal_block([
            ("UNDER SEAL", "sealsmall"),
            ("A question paper leaks weeks<br/>before the paper exists.", "sealbig"),
            ("This document explains what SecureLock does about that,<br/>"
             "assuming you know nothing about computers.", "sealsmall"),
        ]),
        Spacer(1, 6 * mm),
        P("Written for exam board officials, controllers of examination, "
          "administrators, and anyone who has to understand this system well "
          "enough to explain it to somebody else. There is no prior technical "
          "knowledge assumed anywhere in these pages. Every technical word is "
          "explained the first time it appears, and again in the glossary at "
          "the end.", "body"),
        P("SecureLock is a working prototype built for the Smart India "
          "Hackathon. It runs entirely on one laptop, with no internet "
          "connection.", "small"),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    # ------------------------------------------------------ 1. the problem
    f += [
        H("1. The problem, as it actually happens", 1),
        P("When people hear that an examination paper has leaked, they usually "
          "picture the finished paper being stolen &mdash; a sealed envelope opened "
          "early, a PDF copied off a computer the night before the exam."),
        P("That does happen. But it is not where most of the risk lives."),
        P("A question paper is not born finished. It is assembled over weeks. "
          "A professor writes a question at home. She emails it to a colleague "
          "for a second opinion. He pastes it into a shared document. Someone "
          "prints a draft to read on a train. A coordinator collects thirty "
          "questions into one file and sends it around for approval."),
        P("By the time a paper exists as a single document worth guarding, its "
          "contents have already lived on a dozen laptops, in several inboxes, "
          "and in at least one printout that nobody can now account for."),
        callout(
            "The sentence worth remembering",
            "Most systems protect the finished question paper. But the paper "
            "can be compromised long before it exists &mdash; while the individual "
            "questions are still being written and passed around."),
        P("So the useful question is not <i>how do we guard the final file?</i> "
          "It is <i>how do we account for every question, from the moment "
          "somebody types it, to the moment the exam begins?</i>"),

        H("2. Why the usual protections are not enough", 1),
        P("Three defences are normally offered. Each is reasonable, and each "
          "has a specific hole."),
        table([
            ["The usual protection", "Where it falls short"],
            ["<b>Put the paper on a secure server with passwords</b>",
             "It protects the file once it exists, and does nothing for the "
             "weeks before. It also does nothing about the person who is "
             "<i>supposed</i> to have access."],
            ["<b>Keep an access log of who opened what</b>",
             "A log is a file on the same server. Whoever administers that "
             "server can edit the log. A record that the record-keeper can "
             "quietly rewrite is not evidence."],
            ["<b>Lock the paper with a timer until exam day</b>",
             "A timer has to read a clock. If it reads the server's clock, "
             "whoever runs the server can move it. If it reads the user's "
             "clock, any user can move it &mdash; changing your laptop's date is "
             "not a hack, it is a settings screen."],
        ], [62 * mm, PAGE_W - 2 * MARGIN - 62 * mm]),
        P("Notice that all three holes are the same shape. Each protection "
          "depends on somebody trustworthy &mdash; an administrator, a server, a "
          "clock under someone's control. The protection is only ever as good "
          "as the most privileged person in the room."),

        H("3. The idea, in one sentence", 1),
        Paragraph("SecureLock secures the whole life of a question &mdash; not just "
                  "the finished paper &mdash; and moves the two decisions that "
                  "insiders can quietly corrupt, the record of what happened "
                  "and the moment of release, somewhere no single "
                  "administrator can reach.", S["quote"]),
        P("Everything in the rest of this document is a consequence of that "
          "sentence."),
        PageBreak(),
    ]

    # ------------------------------------------------- 4. the ideas needed
    f += [
        H("4. Six ideas you need, in plain language", 1),
        P("These are the only technical concepts in the system. Each one is "
          "ordinary; the contribution is the combination."),

        H("Encryption, and why every question gets its own lock", 3),
        P("Encryption scrambles text so it is unreadable without a key. Think "
          "of a locked box: the box can sit on any shelf, in any office, and "
          "its contents stay private as long as the key is elsewhere."),
        P("SecureLock does something less obvious. It does not put the whole "
          "paper in one box. <b>Every single question gets its own box and its "
          "own key.</b> Steal one key and you have one question. There is no "
          "master moment where everything is readable at once."),
        P("The original, readable text of a question is never written to the "
          "database at all. Only the locked box is stored."),

        H("A fingerprint for text", 3),
        P("A <b>hash</b> is a short code calculated from a piece of text &mdash; a "
          "fingerprint. SecureLock uses one called SHA-256, which always "
          "produces 64 characters, like this:"),
        Paragraph("dc1e889d5def4ac244b4afc90dac11430ecd11ad3debbcad137d9fa7463cf371",
                  S["mono"]),
        P("Two properties make it useful. First, change anything at all in the "
          "question &mdash; one comma &mdash; and the fingerprint changes completely, so "
          "any edit is obvious. Second, it only works forwards: you can "
          "calculate the fingerprint from the question, but you cannot "
          "reconstruct the question from the fingerprint."),
        P("That second property is what makes it safe to publish. A "
          "fingerprint proves a question existed in an exact form at an exact "
          "time, while revealing nothing whatsoever about what the question "
          "says."),

        H("A record that cannot be quietly rewritten", 3),
        P("Every action in SecureLock &mdash; a question written, read, refused, "
          "approved &mdash; is written to a log. The trick is in how the entries "
          "are joined: <b>each entry contains the fingerprint of the entry "
          "before it.</b>"),
        P("This makes the log a chain. If somebody edits entry number 40, its "
          "fingerprint changes, so entry 41 no longer matches what it claims "
          "to follow, and neither does anything after it. You cannot alter one "
          "line quietly. You would have to rewrite every line that came after "
          "it &mdash; and the system checks the whole chain on demand."),

        H("The shared notebook (this is the blockchain part)", 3),
        P("A blockchain is a record that many independent machines keep a copy "
          "of, where entries can only be added at the end and never edited. "
          "Because everyone holds a copy, one person changing their own copy "
          "changes nothing; it just makes their copy disagree with everyone "
          "else's."),
        callout(
            "The most common misunderstanding",
            "The questions are <b>not</b> on the blockchain. No question text, "
            "no answers, no keys, and no personal data ever go anywhere near "
            "it. Only fingerprints, anonymous identifiers, timestamps, and the "
            "release condition. If the entire blockchain were published "
            "tomorrow, nobody would learn a single exam question from it.",
            VERDIGRIS),
        P("So why use it at all? For exactly one reason: it is a place to put "
          "a record where the person who administers our database cannot reach "
          "it. That is the whole benefit, and it is a real one."),

        H("A rule that enforces itself", 3),
        P("A <b>smart contract</b> is a small program stored in that shared "
          "notebook. Once it is there, it runs by itself, the same way for "
          "everybody, and nobody &mdash; including the people who built "
          "SecureLock &mdash; can talk it out of its rules."),
        P("SecureLock uses one to hold the paper: <i>do not permit this paper "
          "to be opened before this moment.</i> It is not a promise made by "
          "our software. It is a condition enforced somewhere else."),

        H("Whose clock decides", 3),
        P("This is the subtle part, and it is worth getting right, because it "
          "is the part judges and officials ask about."),
        P("The smart contract does not read your laptop's clock, and it does "
          "not read our server's clock. It reads the <b>blockchain's own "
          "clock</b> &mdash; a timestamp agreed by the whole network as it records "
          "entries."),
        P("The practical consequence is simple and can be tested in front of "
          "you: set your computer's date forward to the year 2099 and ask for "
          "the paper. The answer is still no, and the refusal is recorded."),
        PageBreak(),
    ]

    # ---------------------------------------------- 5. life of a paper
    f += [
        H("5. The life of one question paper", 1),
        P("Here is the whole system in order. Nothing else happens; this is "
          "the complete journey."),
        table([
            ["Stage", "What happens", "What it leaves behind"],
            ["<b>1. Written</b>",
             "A setter types a question. It is locked with its own key before "
             "it is stored. The readable text is never saved.",
             "A locked box, and a fingerprint."],
            ["<b>2. Identified</b>",
             "The fingerprint is recorded in the shared notebook, along with "
             "an anonymous marker for who wrote it and when.",
             "Proof this question existed in this exact form at this time."],
            ["<b>3. Guarded</b>",
             "Another setter tries to open it and is refused. So is the "
             "administrator. Permission is checked on the server every time.",
             "A recorded refusal &mdash; denials are evidence too."],
            ["<b>4. Reviewed</b>",
             "A reviewer can read and approve, but can never edit. Once "
             "approved, the question is frozen &mdash; even against its author.",
             "An approval, by a named role, at a known time."],
            ["<b>5. Assembled</b>",
             "The system builds a paper from the approved pool, balancing "
             "topics and difficulty, avoiding near-duplicates, and spreading "
             "authorship across setters.",
             "A paper nobody chose by hand &mdash; so no setter knows which of "
             "their questions was used, or against what."],
            ["<b>6. Sealed</b>",
             "The finished paper is locked, its fingerprint recorded, and a "
             "release time attached to it in the smart contract.",
             "A sealed paper and a public, checkable opening time."],
            ["<b>7. Refused</b>",
             "Anyone asking for the paper early is refused &mdash; including the "
             "authority who sealed it, and including anyone who has changed "
             "their computer's clock.",
             "More recorded refusals."],
            ["<b>8. Opened</b>",
             "Once the blockchain's own clock passes the release time, the "
             "contract permits the release and the paper is unlocked.",
             "A release nobody could bring forward."],
        ], [24 * mm, 74 * mm, PAGE_W - 2 * MARGIN - 98 * mm]),

        H("6. Who is allowed to do what", 1),
        P("Different people see genuinely different systems. This is enforced "
          "on the server for every single request &mdash; not by hiding buttons, "
          "which would be no protection at all."),
        table([
            ["Role", "Can", "Cannot"],
            ["<b>Question Setter</b>", "Write their own questions",
             "See anyone else's question, or any assembled paper"],
            ["<b>Reviewer</b>", "Read questions and approve them",
             "Edit a question, ever"],
            ["<b>Exam Authority</b>", "Assemble, seal and release papers",
             "Open a sealed paper early"],
            ["<b>Auditor</b>", "Verify every fingerprint and provenance record",
             "Read the text of any question"],
            ["<b>Super Admin</b>", "Manage user accounts and inspect the audit trail",
             "Read question content &mdash; the highest-privileged account in the "
             "system is deliberately not the most powerful one"],
        ], [30 * mm, 52 * mm, PAGE_W - 2 * MARGIN - 82 * mm]),
        P("That last row is the one worth pausing on. In most systems the "
          "administrator can see everything. Here, the administrator manages "
          "the system without being able to read what it protects.", "small"),
        PageBreak(),
    ]

    # ------------------------------------------- 7. honesty and pitch
    f += [
        H("7. Why blockchain here &mdash; and where it is not the answer", 1),
        P("It would be easy, and wrong, to say &ldquo;we used blockchain, therefore "
          "it is secure.&rdquo; Blockchain is used in exactly two places, for "
          "reasons that can be stated plainly."),
        bullets([
            "<b>For the record of what happened.</b> A database administrator "
            "can rewrite database history. They cannot rewrite the shared "
            "notebook, so a tampered record no longer matches its anchor and "
            "the mismatch is detectable.",
            "<b>For the release condition.</b> A server clock can be changed "
            "by whoever runs the server. The blockchain's clock cannot be "
            "changed by that person, or by an end user on their own device.",
        ]),
        P("Everything else &mdash; accounts, encrypted content, searching, the "
          "detailed audit metadata &mdash; lives in an ordinary database, because "
          "for those jobs an ordinary database is the correct tool and a "
          "blockchain would be a slower, worse one."),

        H("8. What SecureLock does not claim", 1),
        P("Being straight about the limits is more persuasive than "
          "overclaiming, and an official who repeats an overclaim in public "
          "will regret it."),
        table([
            ["The claim we do <b>not</b> make", "What is actually true"],
            ["&ldquo;Leak-proof&rdquo;",
             "Somebody authorised to read a question can photograph the "
             "screen. No software prevents that. The goal is to reduce "
             "exposure and make access traceable."],
            ["&ldquo;It proves who read a question&rdquo;",
             "It proves an authorised account requested it through this "
             "system, at a recorded moment. A person and an account are not "
             "the same thing."],
            ["&ldquo;The blockchain clock is perfectly accurate&rdquo;",
             "It has some tolerance. The honest claim is narrower and still "
             "strong: an end user cannot move it from their own device."],
            ["&ldquo;AI secures the paper&rdquo;",
             "The assembly engine makes a paper less predictable. That is a "
             "change in the odds, not a guarantee &mdash; and it follows fixed "
             "rules rather than being a language model."],
            ["&ldquo;It works even if the blockchain is down&rdquo;",
             "If the network is unreachable, release is refused rather than "
             "falling back to a server clock. That is the safe direction to "
             "fail, and it is a real operational constraint."],
        ], [46 * mm, PAGE_W - 2 * MARGIN - 46 * mm]),
        P("What is claimed: tamper-evident records, defence in depth, "
          "traceable provenance, a blockchain-enforced release, and insider "
          "risk that is reduced and &mdash; when something does happen &mdash; "
          "investigable."),

        H("9. Explaining it in sixty seconds", 1),
        P("If you have one minute and a non-technical audience, this works:"),
        callout(
            "The sixty-second version",
            "&ldquo;Exam papers don't usually leak from the sealed envelope. They "
            "leak weeks earlier, while the questions are still being written "
            "and emailed around. SecureLock locks every question separately "
            "the moment it's typed &mdash; each with its own key, so there's never "
            "a moment when everything is readable at once.<br/><br/>"
            "Every hand-off is recorded in a log where each entry is sealed to "
            "the one before it, so a single line can't be quietly edited. And "
            "the finished paper is held shut by a rule stored on a blockchain, "
            "which decides the opening moment using its own clock &mdash; not our "
            "server's, and not yours. You can change your computer's date to "
            "2099 in front of me, ask for the paper, and it will still say "
            "no.<br/><br/>"
            "We're not claiming it's leak-proof &mdash; anyone who can see a "
            "question can photograph it. We're claiming that every access is "
            "traceable, tampering is visible, and no single administrator can "
            "open the paper early.&rdquo;",
            VERDIGRIS),

        H("10. Glossary", 1),
        table([
            ["Word", "Meaning"],
            ["<b>Encryption</b>", "Scrambling text so it is unreadable without the key."],
            ["<b>AES-256-GCM</b>", "The specific, standard method used to do that."],
            ["<b>Key</b>", "The secret that unlocks one encrypted item."],
            ["<b>Hash / SHA-256</b>",
             "A 64-character fingerprint of a piece of text. Changes completely "
             "if the text changes; cannot be reversed."],
            ["<b>Blockchain</b>",
             "A shared, append-only record kept by many machines, so no single "
             "one of them can rewrite history."],
            ["<b>Smart contract</b>",
             "A small self-enforcing program stored on the blockchain."],
            ["<b>Time lock</b>",
             "The rule that refuses to release the paper before a set moment."],
            ["<b>block.timestamp</b>",
             "The blockchain's own clock &mdash; the one the time lock reads."],
            ["<b>Provenance</b>",
             "The recorded history of where something came from and who "
             "handled it."],
            ["<b>Audit trail</b>",
             "The chained log of everything that happened, including refusals."],
            ["<b>Hash chain</b>",
             "A log where each entry carries the fingerprint of the previous "
             "one, so edits break the chain."],
        ], [38 * mm, PAGE_W - 2 * MARGIN - 38 * mm]),
    ]

    doc.build(f)
    print("built", (OUT / "SecureLock_Explained.pdf").name)


# ================================================================ DOCUMENT 2
def build_manual():
    doc = Doc(OUT / "SecureLock_User_Manual.pdf",
              "SecureLock - User Manual", "User manual")
    f = []

    f += [
        Spacer(1, 30 * mm),
        Paragraph("SecureLock", S["title"]),
        Paragraph("User manual: running and demonstrating the prototype",
                  S["subtitle"]),
        Spacer(1, 12 * mm),
        seal_block([
            ("OPERATOR'S GUIDE", "sealsmall"),
            ("Start it, drive it, and show<br/>somebody why it works.", "sealbig"),
            ("Every command in this manual has been run on a clean machine.", "sealsmall"),
        ]),
        Spacer(1, 6 * mm),
        P("This manual assumes you can open a terminal and type a command, and "
          "nothing beyond that. Part A gets the system running. Part B is a "
          "guided demonstration you can perform in front of an audience. Part C "
          "documents every screen. Part D is what to do when something breaks."),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    # ------------------------------------------------------------- part A
    f += [
        H("Part A &mdash; Getting it running", 1),

        H("A1. What you need", 2),
        table([
            ["Requirement", "Notes"],
            ["<b>Node.js 18 or newer</b>", "Runs the blockchain and the web app."],
            ["<b>Python 3.11, 3.12 or 3.13</b>",
             "<b>Not 3.14.</b> A required library cannot be built on 3.14 and pip "
             "fails with a long Rust error. On a Mac: <font face='Courier'>brew "
             "install python@3.13</font>"],
            ["<b>Nothing else</b>",
             "No internet, no API keys, no database server, no Docker. The "
             "whole system runs offline on one machine."],
        ], [46 * mm, PAGE_W - 2 * MARGIN - 46 * mm]),

        H("A2. Start everything with one command", 2),
        P("From the project folder:"),
        code(["./scripts/start.sh       # macOS and Linux",
              ".\\scripts\\start.ps1     # Windows"]),
        P("The first run takes a few minutes because it installs dependencies "
          "and seeds the demo data. Later runs take seconds. The script checks "
          "your Python version before doing anything, reuses any service that "
          "is already running, and prints the addresses when it is done."),

        H("A3. What is now running", 2),
        P("Three services. All three are needed; stopping any one breaks the "
          "system in a visible way."),
        table([
            ["Service", "Address", "If you stop it"],
            ["<b>Blockchain</b>", "127.0.0.1:8545",
             "The seal goes dark, the countdown stops, and release is refused "
             "rather than falling back to a server clock."],
            ["<b>API</b>", "127.0.0.1:8000",
             "Every signed-in page shows nothing."],
            ["<b>Web app</b>", "localhost:3000",
             "The site itself is gone."],
        ], [28 * mm, 38 * mm, PAGE_W - 2 * MARGIN - 66 * mm], mono_cols=(1,)),
        P("The API also publishes its own interactive documentation at "
          "<font face='Courier'>127.0.0.1:8000/docs</font>, where every "
          "endpoint can be called directly. Useful for proving that the web "
          "app is not faking anything.", "small"),

        H("A4. Signing in", 2),
        P("Open <font face='Courier'>http://localhost:3000</font>. The landing "
          "page needs no account. Click <b>Open the register</b>, then click "
          "any demo account row to fill the form, and press <b>Sign in</b>."),
        P("The password for every demo account is "
          "<font face='Courier'>SecureLock#2026</font>. It is deliberately "
          "obvious: this is local demonstration data, not a real credential."),
        table([
            ["Account", "Role", "Use it to show"],
            ["authority@securelock.demo", "Exam Authority",
             "Assembling, sealing and releasing papers"],
            ["setter1@securelock.demo", "Question Setter",
             "How little a setter can see"],
            ["reviewer@securelock.demo", "Reviewer",
             "Approving without ever being able to edit"],
            ["auditor@securelock.demo", "Auditor",
             "Verifying fingerprints without reading questions"],
            ["admin@securelock.demo", "Super Admin",
             "Managing users &mdash; and the tamper demonstration"],
        ], [56 * mm, 28 * mm, PAGE_W - 2 * MARGIN - 84 * mm], mono_cols=(0,)),
        PageBreak(),
    ]

    # ------------------------------------------------------------- part B
    f += [
        H("Part B &mdash; The guided demonstration", 1),
        P("Eight beats, about ten minutes. Beat 3 is the one to spend time on; "
          "everything else is context for it."),

        H("Beat 1 &mdash; The landing page, before signing in", 2),
        P("<b>Do:</b> open <font face='Courier'>http://localhost:3000</font> "
          "and point at the dark panel."),
        P("<b>Say:</b> that panel is not reading our server. It is reading the "
          "blockchain directly from the browser. The top clock is the chain's "
          "own time and the block number climbs while you watch. The bottom "
          "clock is this laptop's, printed and struck through, because nothing "
          "in the system consults it."),

        H("Beat 2 &mdash; A paper under seal", 2),
        P("<b>Do:</b> sign in as <b>authority</b>. The dashboard opens."),
        P("<b>Say:</b> the dark block is a real sealed paper, with its "
          "fingerprint and the hour it opens. Everything else on the page is "
          "quiet; the sealed object is the only thing rendered in ink, because "
          "sealed means you cannot see inside."),

        H("Beat 3 &mdash; Attack the clock (the important one)", 2),
        P("<b>Do:</b> open <b>Time Lock</b>. Press <b>Year 2099</b>, then press "
          "<b>Attempt decryption</b>."),
        P("<b>Expect:</b> a refusal, stating how many seconds remain according "
          "to blockchain time."),
        callout(
            "What to say here",
            "&ldquo;I have just told the application that it is the year 2099. It "
            "believed me &mdash; look, the device clock says 2099. And the answer is "
            "still no, because the contract never asked this computer what time "
            "it was. That button calls the real decryption endpoint, not a "
            "mock. The refusal has just been written into the audit trail.&rdquo;"),

        H("Beat 4 &mdash; Permission is real, not hidden buttons", 2),
        P("<b>Do:</b> sign out, sign in as <b>setter1</b>, and look at the "
          "navigation. Open <b>Question Vault</b> and try to open a question "
          "written by another setter."),
        P("<b>Expect:</b> a refusal, which is itself recorded."),
        P("<b>Say:</b> the setter is not simply being shown fewer buttons. The "
          "server checks permission on every request, so typing the address "
          "directly fails in exactly the same way."),

        H("Beat 5 &mdash; Review without the power to edit", 2),
        P("<b>Do:</b> sign in as <b>reviewer</b> and open <b>Review Queue</b>. "
          "Approve a question."),
        P("<b>Say:</b> READ, WRITE and APPROVE are three independent "
          "permissions. A reviewer holds two of them and never the third. Once "
          "approved, a question is frozen &mdash; including against the person who "
          "wrote it."),

        H("Beat 6 &mdash; Assemble a paper", 2),
        P("<b>Do:</b> back as <b>authority</b>, open <b>Paper Builder</b> and "
          "generate a paper."),
        P("<b>Say:</b> nobody chose these questions by hand. The engine "
          "balanced the blueprint, avoided near-duplicates, and spread the "
          "authorship across setters &mdash; so no setter knows which of their "
          "questions was used, or alongside what."),

        H("Beat 7 &mdash; Break the audit trail on purpose", 2),
        P("<b>Do:</b> sign in as <b>admin</b>, open <b>Audit Trail</b>, confirm "
          "the chain reports intact, then use the tamper demonstration to alter "
          "one historical row."),
        P("<b>Expect:</b> <b>TAMPERING DETECTED</b>, naming the broken link. "
          "The same screen restores it afterwards."),
        P("<b>Say:</b> each entry carries the fingerprint of the one before it. "
          "Editing a single line breaks every link after it, so a quiet "
          "correction is impossible."),

        H("Beat 8 &mdash; Show that the chain is real", 2),
        P("<b>Do:</b> open <b>Blockchain</b>."),
        P("<b>Say:</b> the left column is what we submitted; the right column "
          "is read back off the chain itself, not from our database. Any "
          "transaction that failed is shown as failed, with the contract's own "
          "reason. Nothing here is invented &mdash; when the chain cannot be "
          "reached, the system records that instead of producing a hash that "
          "would look convincing and mean nothing."),

        H("The automated version of all of this", 2),
        P("If you would rather have the whole flow asserted rather than "
          "clicked, one command runs all of it and checks every outcome:"),
        code(["backend/.venv/bin/python scripts/e2e_demo.py"]),
        P("It finishes with <b>ALL CHECKS PASSED</b> after 56 assertions, "
          "including the 2099 clock attack. The two test suites are:"),
        code(["cd blockchain && npx hardhat test               # 37 contract tests",
              "cd backend && .venv/bin/python -m pytest tests  # 44 backend tests"]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- part C
    f += [
        H("Part C &mdash; Every screen", 1),
        P("The navigation changes with the role, because each role is given a "
          "genuinely different system. Not every account sees every entry "
          "below."),
        table([
            ["Screen", "What it is for"],
            ["<b>Landing page</b>",
             "Public. The live seal, reading the chain directly from the "
             "browser without signing in."],
            ["<b>Dashboard</b>",
             "The state of the register: what is under seal, how many "
             "questions exist, how many access attempts were refused, and the "
             "most recent entries."],
            ["<b>Question Vault</b>",
             "Every question as metadata and fingerprint only. Opening one "
             "requires permission and is recorded."],
            ["<b>Create Question</b>",
             "Write a new question. It is encrypted and fingerprinted before "
             "storage, and anchored on the chain."],
            ["<b>Review Queue</b>",
             "Questions awaiting approval. Approve or reject; never edit."],
            ["<b>Variations</b>",
             "Rule-based rewordings of a question, gated behind a reviewer. "
             "Restates the instruction without touching the substance, which "
             "is why the expected answer cannot drift."],
            ["<b>Paper Builder</b>",
             "Assemble a paper against the blueprint. Shows compliance, "
             "duplicate risk, per-question selection reasoning and contributor "
             "spread."],
            ["<b>Papers</b>",
             "Every paper and its lifecycle status: draft, encrypted, "
             "registered, sealed, released."],
            ["<b>Time Lock</b>",
             "The demonstration. Two clocks, the clock-attack presets, and a "
             "button that calls the real decryption endpoint."],
            ["<b>Audit Trail</b>",
             "Every event, hash-chained. Includes the integrity check and the "
             "tamper demonstration."],
            ["<b>Blockchain</b>",
             "Submitted transactions beside events read back from the chain, "
             "plus the deployed contract addresses."],
            ["<b>Security</b>",
             "The posture summary: refusals, permission grants and integrity "
             "checks in one place."],
        ], [36 * mm, PAGE_W - 2 * MARGIN - 36 * mm]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- part D
    f += [
        H("Part D &mdash; When something goes wrong", 1),

        H("D1. Resetting the demo", 2),
        callout(
            "Read this before you reset anything",
            "Reset the database and the chain <b>together</b>, using "
            "<font face='Courier'>./scripts/reset_demo.sh</font>. Never reset "
            "just one.<br/><br/>"
            "Identifiers like PAPER-2026-001 are regenerated from the start "
            "when the database is reseeded, but the chain still holds the "
            "previous run's records under those same identifiers. The "
            "contracts then refuse everything that follows &mdash; and most "
            "visibly, <b>no new paper can ever be sealed again</b>. The "
            "contracts are right to refuse. The mistake is resetting one half "
            "of a two-part system."),
        code(["# Fresh chain, redeployed contracts, reseeded database.",
              "./scripts/reset_demo.sh"]),

        H("D2. Common problems", 2),
        table([
            ["Symptom", "Cause and fix"],
            ["<b>pip fails with a long Rust error mentioning PyO3</b>",
             "You are on Python 3.14. Install 3.11-3.13, delete "
             "<font face='Courier'>backend/.venv</font>, and run start.sh "
             "again."],
            ["<b>&ldquo;Nothing is under seal right now&rdquo; on the dashboard</b>",
             "There is no sealed paper &mdash; either it has been released, or none "
             "was made. Assemble one in Paper Builder, encrypt it, then "
             "register it with a release time."],
            ["<b>Sealing a paper fails with PaperAlreadyRegistered</b>",
             "The database was reset without the chain. Run "
             "<font face='Courier'>./scripts/reset_demo.sh</font>."],
            ["<b>Everything logs you out at once</b>",
             "The database was reseeded, so the accounts are new. Sign in "
             "again."],
            ["<b>The site loads as a blank dark page</b>",
             "A production build was run while the development server was "
             "live, and they share a folder. Stop the site, delete "
             "<font face='Courier'>frontend/.next</font>, and start again."],
            ["<b>A port is already in use</b>",
             "Something is still running from last time. "
             "<font face='Courier'>./scripts/stop.sh</font>"],
            ["<b>e2e_demo.py reports &ldquo;Seeded near-duplicates detected&rdquo;</b>",
             "The question pool has already been partly used by an earlier "
             "paper, so the run had fewer questions to choose between. Run "
             "<font face='Courier'>./scripts/reset_demo.sh</font> first. The "
             "demonstration needs a full pool; seal your demo paper "
             "<i>after</i> the end-to-end run, not before."],
            ["<b>The seal shows &ldquo;chain unreachable&rdquo;</b>",
             "The blockchain is not running. This is the honest failure mode, "
             "not a bug: release is refused rather than falling back to a "
             "server clock. Start it with start.sh."],
        ], [52 * mm, PAGE_W - 2 * MARGIN - 52 * mm]),

        H("D3. Stopping everything", 2),
        code(["./scripts/stop.sh"]),
        P("This leaves the database and the chain state on disk, so starting "
          "again resumes exactly where you left off. Use reset_demo.sh instead "
          "when you want to begin from a clean slate.", "small"),

        H("D4. Where things live", 2),
        table([
            ["Path", "What it holds"],
            ["backend/", "The API, encryption, permissions, audit chain, seed data"],
            ["blockchain/", "The two smart contracts and their tests"],
            ["frontend/", "The web app"],
            ["scripts/", "Startup, reset and the end-to-end demonstration"],
            ["docs/", "This manual and the from-scratch explanation"],
            ["backend/securelock.db", "The demo database (safe to delete via reset_demo.sh)"],
            [".logs/", "Output from services started by start.sh"],
        ], [46 * mm, PAGE_W - 2 * MARGIN - 46 * mm], mono_cols=(0,)),
    ]

    doc.build(f)
    print("built", (OUT / "SecureLock_User_Manual.pdf").name)




# ================================================================ DOCUMENT 3
def build_presentation():
    doc = Doc(OUT / "SecureLock_Presentation_Guide.pdf",
              "SecureLock - Presentation Guide", "Presentation guide")
    f = []

    f += [
        Spacer(1, 26 * mm),
        Paragraph("SecureLock", S["title"]),
        Paragraph("Presentation guide &mdash; SIH internal hackathon, round 1",
                  S["subtitle"]),
        Spacer(1, 10 * mm),
        seal_block([
            ("EVERYTHING YOU NEED TO PRESENT", "sealsmall"),
            ("We don't just secure the question<br/>paper. We secure the question.", "sealbig"),
            ("Problem, existing systems, novelty, stack, demo, limitations,<br/>"
             "and the questions judges actually ask.", "sealsmall"),
        ]),
        Spacer(1, 5 * mm),
        P("This guide is written in plain language so any member of the team "
          "can present with it, including someone who did not write the code. "
          "Read sections 1 to 5 if you have ten minutes. Read all of it if you "
          "are the one answering questions."),
        NextPageTemplate("body"),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 1
    f += [
        H("1. The first thirty seconds", 1),
        P("Open with the problem, not the technology. Judges hear "
          "&ldquo;blockchain&rdquo; forty times a day; they hear a sharp problem "
          "statement rarely."),
        callout(
            "Say this, roughly",
            "&ldquo;When an exam paper leaks, everyone pictures the sealed envelope "
            "being opened early. But most leaks don't happen there. They happen "
            "weeks earlier, while the questions are still being written and "
            "emailed between professors &mdash; before a &lsquo;paper&rsquo; even exists to "
            "guard.<br/><br/>"
            "SecureLock secures the whole life of a question, from the moment "
            "somebody types it to the moment the exam begins. And the final "
            "paper is held shut by a rule on a blockchain that decides the "
            "opening moment using its own clock &mdash; not our server's, and not "
            "yours. I can prove that in about thirty seconds.&rdquo;"),
        P("Then go straight to the clock demonstration. Do not save it for the "
          "end; it is the thing they will remember, and it is better shown "
          "early while attention is highest."),

        H("2. The problem statement", 1),
        P("A question paper is not created as a single document. It is "
          "assembled over weeks, by many people:"),
        numbered([
            "A professor writes a question on a personal laptop.",
            "She emails it to a colleague for a second opinion.",
            "He pastes it into a shared document with his own suggestions.",
            "Somebody prints a draft to read on the way home.",
            "A coordinator collects thirty questions into one file and "
            "circulates it for approval.",
            "Only now does a &ldquo;question paper&rdquo; exist &mdash; and only now do most "
            "security systems start protecting it.",
        ]),
        P("By that point the content has lived on many machines, in several "
          "inboxes, and in at least one printout nobody can account for. Every "
          "one of those steps is a leak opportunity, and none of them is "
          "recorded anywhere that survives a determined insider."),
        P("There is a second problem underneath the first. Even a perfectly "
          "guarded paper has to be <i>released</i> at some moment, and "
          "something has to decide when that moment has arrived. Whatever "
          "makes that decision becomes the weakest point in the system."),
        callout(
            "The problem in one line",
            "Protect every question from the moment it is written &mdash; and make "
            "the release decision something no single person can move.",
            VERDIGRIS),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 3
    f += [
        H("3. How papers are protected today, and where each protection breaks", 1),
        P("These are the approaches currently in use across boards and "
          "universities. Each is sensible. Each has a specific hole, and the "
          "holes are all the same shape: they depend on trusting whoever holds "
          "the most privilege."),
        table([
            ["What is used today", "How it works", "Where it breaks"],
            ["<b>Sealed physical packets</b>",
             "Papers printed at a confidential press, sealed, moved under "
             "escort, stored in a strongroom, opened at a fixed hour before "
             "witnesses.",
             "Protects the printed paper only. The questions existed digitally "
             "for weeks beforehand, entirely outside this protection."],
            ["<b>Confidential printing presses</b>",
             "A small trusted vendor prints under supervision.",
             "Concentrates trust in one organisation, and again begins after "
             "the questions are already written."],
            ["<b>Encrypted file with a password released on exam day</b>",
             "Centres receive an encrypted paper in advance; the password is "
             "sent on the morning of the exam.",
             "The encrypted file is already sitting at every centre. Security "
             "rests entirely on one password held by a small group &mdash; and on "
             "them not sending it early."],
            ["<b>Server-side timed release</b>",
             "A central server refuses to hand over the paper until a set time.",
             "The server's clock is set by whoever administers the server. "
             "An insider with that access can bring the release forward, and "
             "the logs that would show it are on the same server."],
            ["<b>ERP exam modules with roles and audit logs</b>",
             "Role-based access, with a database log of who did what.",
             "The log is a database table. A database administrator can edit "
             "it. A record that its own keeper can quietly rewrite is not "
             "evidence."],
        ], [40 * mm, 56 * mm, PAGE_W - 2 * MARGIN - 96 * mm]),
        P("Notice the pattern. Every one of these protects the <i>final "
          "artefact</i>, and every one leaves at least one person who can "
          "quietly override it &mdash; usually the person best placed to do so "
          "without being noticed.", "small"),

        H("4. What we built", 1),
        P("SecureLock is a working prototype, not a slide deck. It runs "
          "offline on one laptop and does all of the following, verified by "
          "automated tests:"),
        bullets([
            "Encrypts <b>every question separately</b>, each with its own key, "
            "at the moment it is written. The readable text is never stored.",
            "Gives every question a <b>fingerprint</b> (SHA-256) and records "
            "that fingerprint on a blockchain, along with an anonymous marker "
            "for who wrote it and when.",
            "Treats <b>READ, WRITE and APPROVE as three separate "
            "permissions</b>, checked on the server for every request &mdash; a "
            "reviewer can approve without ever being able to edit.",
            "Assembles the paper automatically from the approved pool, "
            "balancing the blueprint, avoiding near-duplicates and spreading "
            "authorship, so <b>no setter can predict which of their questions "
            "was used</b>.",
            "Seals the finished paper and registers it with a release time in "
            "a <b>smart contract</b>, which then refuses to permit release "
            "until the blockchain's own clock passes that time.",
            "Records every action &mdash; including every refusal &mdash; in a "
            "<b>hash-chained audit log</b> where editing one row breaks every "
            "row after it, visibly.",
        ]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 5, 6
    f += [
        H("5. What is genuinely new", 1),
        P("Be honest here. AES, SHA-256 and smart contracts are ordinary, "
          "well-known technology. Claiming to have invented them would be "
          "caught instantly. The contribution is <b>where</b> they are applied "
          "and <b>what is deliberately left out</b>."),
        table([
            ["Novelty", "Why it matters"],
            ["<b>The question is the unit of security, not the paper</b>",
             "Everything else on the market starts protecting at the point a "
             "paper exists. We start at the keystroke. This is the core idea "
             "and the whole reason the system is shaped the way it is."],
            ["<b>Per-question keys, not one paper key</b>",
             "There is never a moment when one secret unlocks everything. "
             "Compromising one key costs one question."],
            ["<b>The release condition is not ours to move</b>",
             "The decision lives in a smart contract and reads "
             "<font face='Courier'>block.timestamp</font>. Not our server "
             "clock, not the user's device. No administrator on our side can "
             "bring an exam paper forward."],
            ["<b>Refusals are first-class evidence</b>",
             "Most systems log successes. We record every denial and anchor "
             "it. An investigation usually needs the attempts that failed, "
             "not the ones that worked."],
            ["<b>Blockchain used in exactly two places, and argued for</b>",
             "Only the provenance anchor and the release condition. Everything "
             "else is an ordinary database, because for those jobs a database "
             "is the correct tool. Being able to say where blockchain is "
             "<i>not</i> used is itself unusual."],
            ["<b>It fails honestly</b>",
             "If the chain is unreachable, the system refuses release rather "
             "than falling back to a server clock, and records the attempt "
             "instead of inventing a transaction hash that would look "
             "convincing and mean nothing."],
        ], [56 * mm, PAGE_W - 2 * MARGIN - 56 * mm]),

        H("6. Technology stack", 1),
        P("Every choice below is boring on purpose. Nothing here is "
          "experimental, because an examination system is not the place for "
          "novelty in the plumbing."),
        table([
            ["Layer", "What we used", "Why"],
            ["<b>Smart contracts</b>",
             "Solidity 0.8.24, OpenZeppelin AccessControl 5.1, Hardhat 2.22",
             "Two contracts: QuestionRegistry (provenance) and PaperTimeLock "
             "(release). OpenZeppelin because writing your own access control "
             "is how contracts get broken."],
            ["<b>Blockchain</b>", "Local EVM chain (Hardhat), chain ID 31337",
             "Runs offline, needs no internet, no faucet and no real currency. "
             "Any EVM-compatible network works by changing one setting."],
            ["<b>Backend</b>",
             "Python 3.11-3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10",
             "FastAPI gives typed request validation and interactive API docs "
             "for free, which matters when judges ask to see the real "
             "endpoint."],
            ["<b>Cryptography</b>",
             "AES-256-GCM and SHA-256 via <font face='Courier'>cryptography</font> "
             "44; Argon2id for passwords; JWT for sessions",
             "Standard primitives from a maintained library. We never "
             "hand-roll cryptography. GCM also detects tampering with the "
             "ciphertext itself."],
            ["<b>Database</b>", "SQLite by default, PostgreSQL supported",
             "No database server to install for the demo; one setting switches "
             "to PostgreSQL for anything real."],
            ["<b>Chain access</b>", "web3.py 7.6",
             "Submits transactions and reads events back from the chain."],
            ["<b>Web app</b>",
             "Next.js 14, React 18, TypeScript, Tailwind CSS",
             "Sixteen routes. TypeScript so the API contract is checked at "
             "build time rather than during a demo."],
            ["<b>Testing</b>",
             "37 contract tests, 44 backend tests, a 56-assertion end-to-end run",
             "The end-to-end run drives the real HTTP API against the real "
             "chain and asserts every outcome, including the attacks."],
        ], [28 * mm, 54 * mm, PAGE_W - 2 * MARGIN - 82 * mm]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 7, 8
    f += [
        H("7. How the software works", 1),
        P("Three layers, and one rule that holds the whole design together: "
          "<b>content stays off the chain, encrypted; only fingerprints go "
          "on it.</b>"),
        diagram([
            "               WEB APP  (Next.js, 16 routes)",
            "                        |",
            "               API      (FastAPI)",
            "                        |   permissions - encryption",
            "                        |   assembly    - audit chain",
            "             +----------+----------+",
            "             |                     |",
            "        DATABASE               BLOCKCHAIN (EVM)",
            "        accounts               QuestionRegistry.sol",
            "        ciphertext             PaperTimeLock.sol",
            "        wrapped keys           |",
            "        audit log              fingerprints, provenance,",
            "                               release condition",
            "",
            "   plaintext is never          no question text ever",
            "   stored, in any layer        reaches the chain",
        ]),
        P("The life of a paper, in eight stages:"),
        table([
            ["Stage", "What happens"],
            ["<b>1. Written</b>",
             "A setter submits a question. It is encrypted with its own "
             "AES-256-GCM key and fingerprinted before anything is stored."],
            ["<b>2. Anchored</b>",
             "The fingerprint, an anonymous author marker and a timestamp are "
             "written to QuestionRegistry on the chain."],
            ["<b>3. Guarded</b>",
             "Any read is checked against READ/WRITE/APPROVE grants on the "
             "server. Refusals are recorded and anchored."],
            ["<b>4. Reviewed</b>",
             "A reviewer approves. The question is frozen against edits, "
             "including by its author, and the lifecycle change is recorded on "
             "the chain."],
            ["<b>5. Assembled</b>",
             "A seeded optimiser selects questions against the blueprint, "
             "penalises near-duplicates (TF-IDF similarity) and spreads "
             "authorship. The same seed reproduces the same paper, so the "
             "process is auditable."],
            ["<b>6. Sealed</b>",
             "The paper is encrypted, fingerprinted, and registered in "
             "PaperTimeLock with a release time."],
            ["<b>7. Refused</b>",
             "Every early request is refused by the contract &mdash; including from "
             "the authority that sealed it, and including from a device whose "
             "clock has been changed."],
            ["<b>8. Released</b>",
             "Once <font face='Courier'>block.timestamp</font> passes the "
             "release time, the contract permits release and the paper "
             "decrypts."],
        ], [26 * mm, PAGE_W - 2 * MARGIN - 26 * mm]),

        H("8. Who can do what", 1),
        table([
            ["Role", "Can", "Cannot"],
            ["<b>Question Setter</b>", "Write their own questions",
             "See another setter's question, or any paper"],
            ["<b>Reviewer</b>", "Read and approve", "Edit anything, ever"],
            ["<b>Exam Authority</b>", "Assemble, seal, release",
             "Open a sealed paper early"],
            ["<b>Auditor</b>", "Verify fingerprints and provenance",
             "Read any question text"],
            ["<b>Super Admin</b>", "Manage accounts, inspect the audit trail",
             "Read question content"],
        ], [30 * mm, 48 * mm, PAGE_W - 2 * MARGIN - 78 * mm]),
        P("The last row is worth saying out loud to judges: <b>the most "
          "privileged account in the system deliberately cannot read what the "
          "system protects.</b> That is unusual, and it is the direct answer "
          "to &ldquo;what about a corrupt administrator?&rdquo;"),
        PageBreak(),
    ]

    f += _presentation_part_two()
    doc.build(f)
    print("built", (OUT / "SecureLock_Presentation_Guide.pdf").name)


def _presentation_part_two():
    """Sections 9 onwards: running it, demonstrating it, defending it."""
    f = []

    # ------------------------------------------------------------- 9
    f += [
        H("9. Running it from a Mac terminal", 1),
        P("Open Terminal and run three commands. The first two are only needed "
          "once."),
        code([
            "git clone https://github.com/anishc23/sih-qpleak.git",
            "cd sih-qpleak",
            "./scripts/start.sh",
        ]),
        P("That single script checks your versions, installs everything, "
          "starts the local blockchain, deploys both contracts, seeds the demo "
          "data, and starts the API and the web app. First run takes a few "
          "minutes; later runs take seconds."),
        callout(
            "One thing that will bite you on a Mac",
            "You need <b>Python 3.11, 3.12 or 3.13 &mdash; not 3.14</b>. A required "
            "library cannot be built on 3.14 and pip fails with a long, "
            "confusing error. The script checks this first and tells you. "
            "Fix it with:<br/><br/>"
            "<font face='Courier'>brew install python@3.13</font>"),
        P("Then open <font face='Courier'>http://localhost:3000</font>."),
        P("Useful afterwards:"),
        code([
            "backend/.venv/bin/python scripts/e2e_demo.py   # prove the whole flow",
            "./scripts/reset_demo.sh                        # start the demo over",
            "./scripts/stop.sh                              # stop everything",
        ]),

        H("10. Running it from a Windows terminal", 1),
        P("Open PowerShell and run:"),
        code([
            "git clone https://github.com/anishc23/sih-qpleak.git",
            "cd sih-qpleak",
            ".\\scripts\\start.ps1",
        ]),
        P("If PowerShell refuses to run the script, allow local scripts for "
          "this session only and run it again:"),
        code(["Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass"]),
        P("Then open <font face='Courier'>http://localhost:3000</font>."),
        P("To prove the flow on Windows:"),
        code(["backend\\.venv\\Scripts\\python.exe scripts\\e2e_demo.py"]),
        P("Same Python rule applies: install 3.11-3.13 from python.org, not "
          "3.14, and tick &ldquo;Add Python to PATH&rdquo; during installation.", "small"),
        callout(
            "Before you present, on either platform",
            "Run <font face='Courier'>reset_demo.sh</font> (or reseed on "
            "Windows), then run the end-to-end demo <b>first</b>, and only "
            "then seal a fresh paper for the live demonstration. The "
            "end-to-end run needs a full question pool. Never reset the "
            "database without also resetting the chain &mdash; they share "
            "identifiers, and resetting only one means no paper can be sealed "
            "again."),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 11
    f += [
        H("11. The five-minute live demonstration", 1),
        P("The full eight-beat script is in the user manual. If you only have "
          "five minutes, do these four."),
        table([
            ["Beat", "Do", "Say"],
            ["<b>1. The seal</b>",
             "Open the landing page. Do not sign in.",
             "&ldquo;That panel is reading the blockchain directly from the "
             "browser, not our server. The block number is climbing while we "
             "talk. Underneath is this laptop's own clock, struck through, "
             "because nothing consults it.&rdquo;"],
            ["<b>2. The attack</b>",
             "Sign in as the exam authority, open Time Lock, press "
             "<b>Year 2099</b>, then <b>Attempt decryption</b>.",
             "&ldquo;I've just told the system it's the year 2099 and it believed "
             "me. The answer is still no, because the contract never asked "
             "this computer what time it is. That button calls the real API, "
             "not a mock.&rdquo;"],
            ["<b>3. The refusal</b>",
             "Sign in as a question setter and try to open another setter's "
             "question.",
             "&ldquo;This isn't a hidden button. The server checks permission on "
             "every request, and the refusal has just been written into the "
             "audit trail as evidence.&rdquo;"],
            ["<b>4. The tamper</b>",
             "As admin, open Audit Trail, confirm the chain is intact, then "
             "break one row deliberately.",
             "&ldquo;Each entry carries the fingerprint of the one before it. "
             "Editing a single line breaks every line after it &mdash; so a quiet "
             "correction is impossible.&rdquo;"],
        ], [24 * mm, 52 * mm, PAGE_W - 2 * MARGIN - 76 * mm]),
        P("If a judge asks whether the demo is real, open "
          "<font face='Courier'>127.0.0.1:8000/docs</font> and call the "
          "decrypt endpoint directly in front of them. It refuses in exactly "
          "the same way.", "small"),

        H("12. Advantages over what is used today", 1),
        table([
            ["Question", "Current systems", "SecureLock"],
            ["<b>When does protection start?</b>",
             "When the paper exists, days before the exam",
             "At the keystroke, weeks earlier"],
            ["<b>What is the unit of security?</b>",
             "The whole paper, one file, one password",
             "Each question, its own key"],
            ["<b>Can an administrator read the content?</b>",
             "Usually yes",
             "No &mdash; the highest-privileged role cannot read questions"],
            ["<b>Can the log be edited?</b>",
             "Yes, by whoever runs the database",
             "Edits break the hash chain and are detected"],
            ["<b>Who decides the release moment?</b>",
             "A server clock, set by an administrator",
             "A smart contract reading the blockchain's own clock"],
            ["<b>Does changing a device clock help an attacker?</b>",
             "Sometimes yes",
             "No, and the attempt is recorded"],
            ["<b>Are refused attempts recorded?</b>",
             "Rarely",
             "Always, and anchored on chain"],
            ["<b>Can a setter predict the paper?</b>",
             "Often, since selection is manual",
             "No &mdash; seeded automatic assembly across many contributors"],
            ["<b>What happens if the anchor is unreachable?</b>",
             "Usually silent fallback",
             "Release is refused; the failure is recorded, never faked"],
        ], [46 * mm, 50 * mm, PAGE_W - 2 * MARGIN - 96 * mm]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 13, 14
    f += [
        H("13. Limitations, stated plainly", 1),
        P("Say these before a judge finds them. A team that names its own "
          "limits is far more credible than one that is caught out."),
        table([
            ["Limitation", "Our position"],
            ["<b>It cannot stop a photograph</b>",
             "Anyone authorised to read a question can photograph the screen. "
             "No software prevents this. We reduce exposure and make access "
             "traceable."],
            ["<b>A local test chain is not a real trust anchor</b>",
             "The prototype runs a local chain. It demonstrates the mechanism "
             "correctly, but production would need a permissioned or "
             "consortium chain with independent validators."],
            ["<b>The master key is a single point of trust</b>",
             "Whoever holds it can decrypt the database. In production it "
             "belongs in an HSM or cloud KMS; the key-vault interface is three "
             "functions wide precisely so it can be swapped."],
            ["<b>Question variation is rule-based, not AI</b>",
             "It restates the instruction and leaves the substantive clause "
             "untouched, which is exactly why the expected answer cannot "
             "drift. We label it as rule-based throughout."],
            ["<b>Blockchain availability is a hard dependency</b>",
             "If the node is unreachable, release is refused. That is the "
             "correct direction to fail, but it is a real operational "
             "constraint."],
            ["<b>block.timestamp has tolerance</b>",
             "Validators have some leeway. The honest claim is narrower: an "
             "end user cannot move it from their own device."],
            ["<b>An account is not a person</b>",
             "We prove an authorised account acted, not which human was at the "
             "keyboard. Binding accounts to people is an organisational "
             "control, not a software one."],
        ], [50 * mm, PAGE_W - 2 * MARGIN - 50 * mm]),

        H("14. What we would build next", 1),
        bullets([
            "<b>Move to a permissioned chain</b> with validators run by "
            "independent bodies &mdash; the board, a university, an audit "
            "authority &mdash; so no single institution controls the anchor.",
            "<b>Hardware-backed key storage</b> (HSM or cloud KMS) to remove "
            "the single-point-of-trust master key.",
            "<b>Two-person release</b>, requiring two authorised officials to "
            "co-sign before the contract will permit a release.",
            "<b>Per-centre sealed distribution</b>, so each examination centre "
            "receives its own sealed copy with its own release record.",
            "<b>Watermarking per reader</b>, so a photographed question can be "
            "traced back to the account that displayed it.",
        ]),
        PageBreak(),
    ]

    # ------------------------------------------------------------- 15, 16
    f += [
        H("15. Questions judges are likely to ask", 1),
        table([
            ["Question", "Answer"],
            ["<b>Why blockchain? Isn't this just a database?</b>",
             "For most of it, yes &mdash; and we use an ordinary database for most "
             "of it. Blockchain is used in exactly two places where a database "
             "creates a trust problem: the provenance anchor, because a DBA "
             "can rewrite database history; and the release condition, because "
             "a server clock can be changed by whoever runs the server."],
            ["<b>Are the questions stored on the blockchain?</b>",
             "No. Never. Only fingerprints, anonymous identifiers, timestamps "
             "and the release condition. If the entire chain were published, "
             "nobody would learn a single question from it."],
            ["<b>What if the administrator is corrupt?</b>",
             "The Super Admin role cannot read question content at all, cannot "
             "release a paper early, and cannot edit the audit log without "
             "breaking the hash chain. That is the specific attacker we "
             "designed against."],
            ["<b>What if someone changes the server time?</b>",
             "It changes nothing. The contract reads the blockchain's clock. "
             "We can demonstrate the equivalent attack from the client side in "
             "thirty seconds."],
            ["<b>Is this actually running, or mocked?</b>",
             "Running. Every button calls the real API against a real chain. "
             "We can open the API documentation and call the endpoint "
             "directly, and show you real transaction hashes and block "
             "numbers."],
            ["<b>How do you know it works?</b>",
             "37 smart-contract tests, 44 backend tests, and a 56-assertion "
             "end-to-end run that drives the real HTTP API and asserts every "
             "outcome, including the clock attack and tamper detection."],
            ["<b>Does it need internet?</b>",
             "No. It runs entirely offline on one laptop. No API keys, no "
             "cloud services, no cryptocurrency."],
            ["<b>What is the cost of running a blockchain?</b>",
             "Nothing here. A permissioned chain has no transaction fees; the "
             "cost is running nodes, which the participating institutions "
             "would already do. We deliberately hardcode no public network."],
            ["<b>Can it scale to a real board exam?</b>",
             "The database side scales normally. The chain side writes only "
             "small fingerprints, a few per question, so throughput is "
             "modest &mdash; but honest answer: we have tested at prototype scale, "
             "not at board scale."],
        ], [46 * mm, PAGE_W - 2 * MARGIN - 46 * mm]),
        PageBreak(),
    ]

    f += [
        H("16. Presenter's cheat sheet", 1),
        P("One page. Take this to the table."),
        seal_block([
            ("THE ONE LINE", "sealsmall"),
            ("We don't just secure the question paper.<br/>"
             "We secure the question, from creation<br/>to examination.", "sealbig"),
        ]),
        table([
            ["Prompt", "Answer"],
            ["<b>The problem</b>",
             "Papers leak weeks before the paper exists, while questions are "
             "still being written and emailed."],
            ["<b>The idea</b>",
             "Secure the whole life of a question, and move the release "
             "decision somewhere no administrator can reach."],
            ["<b>The proof</b>",
             "Set the clock to 2099, ask for the paper, still refused."],
            ["<b>Where blockchain is used</b>",
             "Two places only: provenance anchor, release condition."],
            ["<b>What is on the chain</b>",
             "Fingerprints, anonymous markers, timestamps. No question text, "
             "ever."],
            ["<b>Roles</b>",
             "Setter, Reviewer, Exam Authority, Auditor, Super Admin &mdash; and "
             "the admin cannot read questions."],
            ["<b>Numbers</b>",
             "37 contract tests, 44 backend tests, 56 end-to-end assertions, "
             "16 web routes, 2 smart contracts."],
            ["<b>Biggest limitation</b>",
             "Cannot stop a photograph. Say it before they ask."],
            ["<b>Start it</b>",
             "Mac: ./scripts/start.sh &nbsp;&nbsp; Windows: .\\scripts\\start.ps1"],
            ["<b>Demo accounts</b>",
             "authority@securelock.demo and four others, password "
             "SecureLock#2026"],
        ], [40 * mm, PAGE_W - 2 * MARGIN - 40 * mm]),
        P("Final advice: lead with the problem, show the clock attack early, "
          "and volunteer your limitations. Judges reward teams who clearly "
          "understand what their system does <i>not</i> do.", "small"),
    ]
    return f


if __name__ == "__main__":
    build_explained()
    build_manual()
    build_presentation()
