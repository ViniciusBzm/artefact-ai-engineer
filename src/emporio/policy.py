"""Small-document retrieval, anchored to the supplied policy PDF page numbers.

No embeddings are necessary for an eight-page manual. Routing and page citations
are explicit and inspectable; canonical summaries are reviewed against version 2.1.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
from dataclasses import dataclass

POLICIES = {
    "address": (2, "Our store is at Rua 14 de Maio, 3200, Centro, Campo Grande/MS, CEP 79202-333. You can reach the store at (67) 3341-4444."),
    "hours": (2, "We open Monday to Friday, 9:00 a.m. to 6:00 p.m., and Saturday, 9:00 a.m. to 1:00 p.m. We are closed on Sundays and public holidays. Special schedules may be announced separately."),
    "contact": (6, "The dedicated WhatsApp channel in section 7 is (67) 3321-4500. The company table also labels (67) 3341-4444 as phone/WhatsApp. Please confirm the intended channel with the team; the source lists both. Service follows store opening hours."),
    "payment": (3, "We accept PIX, debit cards, credit cards and bank slips. PIX offers 5% off the list price, but does not stack with promotions. Bank slips can take up to three business days to clear."),
    "installments": (3, "The manual offers interest-free installments, but its overview and detailed tiers differ. The wording for up to 3 installments and the under-R$ 50 exception is ambiguous, so please confirm those terms with our team. The detailed tiers state R$ 80 minimum per installment for 4-6 and R$ 100 for 7-12. Split payment methods are described for purchases over R$ 2,000. I cannot confirm a specific installment plan from this inconsistent source."),
    "returns": (4, "For online purchases, you may request a change-of-mind return within 7 calendar days of receiving the product. Keep the original packaging, manuals and accessories, without signs of use. The store covers return shipping and refunds via the original payment method within 10 business days. We need the delivery date and purchase channel to assess your specific case."),
    "defects": (4, "The store's manual describes an exchange process for manufacturing defects within 30 calendar days of purchase, followed by manufacturer warranty handling. Separately, the manual recognizes a 90-day statutory warranty. These provisions need human review in an individual dispute; do not treat the 30-day exchange workflow as eliminating statutory rights."),
    "exchange": (4, "Preference-based exchanges (color, model or size) may be requested within 7 days, subject to availability, original packaging and good condition. Price differences may apply. Customized instruments, clearly marked final-sale items, and wind-instrument mouthpieces are excluded by the store's stated policy."),
    "shipping": (4, "Within the Campo Grande metropolitan region, shipping is free above R$ 500 and costs R$ 35 below that amount; exactly R$ 500 is unspecified and needs confirmation from our team. The stated delivery estimate is 1-3 business days. Outside the region, PAC is estimated at 5-12 business days, SEDEX at 2-5 and Jadlog at 3-8. Cost depends on destination and item dimensions; large instruments may need a special quote. These are policy estimates, not a promised arrival date."),
    "tracking": (5, "A tracking code is sent by email and WhatsApp after dispatch. Shipment tracking may be checked with Correios or Jadlog. For a specific order's code or status, please sign in locally with /login and provide the order number. I cannot perform a live carrier lookup."),
    "promotions": (6, "Promotions are non-cumulative: the 5% PIX discount does not apply to an already promotional price. All promotional offers depend on stock. Only promotions marked active in the operational dataset can be offered; expired campaigns are not valid."),
    "warranty": (7, "The manual states a 90-day statutory warranty for manufacturing defects from receipt; manufacturers may offer additional coverage. Damage from misuse or unauthorized modifications is excluded under the stated conditions. Specific claims require a human review."),
    "privacy": (7, "Customer contact details are used to process orders and provide support. Promotional messages require explicit consent. Requests to delete personal data should be directed to customer service; the assistant cannot execute deletion."),
    "accessories": (6, "We specialize in musical instruments only; we do not sell strings, picks, cables, cases, pedals or amplifiers."),
    "complaints": (7, "I'm sorry this happened. Please contact our customer-service team for help with your complaint. The manual states a response window of 24 business hours. I cannot register or forward the complaint, approve a refund, or confirm that someone has been notified."),
}

# Mapping is topic-based, deliberately not a blind vector search over a tiny manual.
SYNONYMS = {
    "address": ["endereco", "onde fica", "localizacao", "address", "where is", "location"],
    "hours": ["horario", "horas", "abre", "fecha", "funcionamento", "opening", "hours", "open", "close"],
    "contact": ["whatsapp", "telefone", "contato", "phone", "contact", "atendente"],
    "installments": ["parcel", "vezes", "installment", "split payment", "12x", "6x", "3x"],
    "payment": ["pix", "pagamento", "boleto", "cartao", "payment", "debit", "credit", "pay"],
    "returns": ["arrepend", "devolver", "devolucao", "return", "refund", "desist", "reembolso", "cancelar compra"],
    "defects": ["defeito", "com defeito", "defective", "broken", "quebrado"],
    "exchange": ["troca", "trocar", "exchange", "outra cor", "outro modelo"],
    "shipping": ["frete", "entrega", "envio", "shipping", "delivery", "transportadora", "correios", "sedex"],
    "tracking": ["rastre", "tracking", "codigo de rast", "codigo do pedido"],
    "promotions": ["promoc", "desconto", "oferta", "discount", "promotion", "sale"],
    "warranty": ["garantia", "warranty", "guarantee"],
    "privacy": ["lgpd", "privacidade", "dados pessoais", "excluir meus dados", "privacy", "delete my data"],
    "accessories": ["palheta", "cabo", "corda avulsa", "amplificador", "pedal", "case", "accessories", "pick", "cable", "strings"],
    "complaints": ["reclamacao", "reclamar", "complaint", "complain", "manager", "gerente", "dispute"],
}


def topic_from_text(question: str) -> str | None:
    from .store import norm
    question = norm(question)
    # Explicit returns first: a question about a return may also mention PIX/payment.
    order = ["privacy", "complaints", "returns", "defects", "exchange", "tracking", "shipping", "installments",
             "promotions", "warranty", "hours", "address", "contact", "privacy", "payment", "accessories"]
    for key in order:
        if any(x in question for x in SYNONYMS[key]):
            return key
    return None


APPROVED_PDF_SHA256 = 'b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7'
APPROVED_DEMO_SHA256 = '56beafcc4406a683bf8227aab6bf8886970e5aa0c5bc1d882010d15e21888a04'
EXTRA_PAGES = {'contact': [2], 'defects': [7], 'shipping': [5], 'privacy': [8]}


@dataclass(frozen=True)
class Passage:
    page: int
    text: str
    digest: str


class PolicyBook:
    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        from .store import norm
        pdfs = [p for p in data_dir.glob('*.pdf') if norm(p.name).endswith('politicas_da_loja.pdf')]
        if len(pdfs) > 1:
            raise ValueError('Ambiguous policy PDF source')
        self.pdf = pdfs[0] if pdfs else None
        self.pages = {}
        self.original_pdf = bool(self.pdf)
        if self.pdf:
            self.digest = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
            if self.digest != APPROVED_PDF_SHA256:
                raise ValueError('Unreviewed policy source: review passages and translations before updating digest')
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise RuntimeError("Original PDF detected: install the [pdf] extra for pypdf") from exc
            reader = PdfReader(self.pdf)
            self.pages = {i + 1: re.sub(r'\s+', ' ', p.extract_text() or '').strip() for i, p in enumerate(reader.pages)}
        else:
            fixture = data_dir / "policies_demo.json"
            if not fixture.exists():
                raise FileNotFoundError("Provide políticas_da_loja.pdf or policies_demo.json in --data-dir")
            # Git may convert LF/CRLF; only line endings are normalized. All
            # policy text changes still require explicit review and re-pinning.
            self.digest = hashlib.sha256(fixture.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
            if self.digest != APPROVED_DEMO_SHA256:
                raise ValueError('Unreviewed demo policy fixture')
            self.pages = {int(k): v for k, v in json.loads(fixture.read_text(encoding="utf-8")).items()}

    def retrieve(self, topic: str) -> list[Passage]:
        """Retrieve reviewed section pages from the actual loaded source.

        The manual is tiny: section routing beats an embedding service here.
        Passages remain local; final text is a reviewed translation, not free LLM prose.
        """
        if topic not in POLICIES:
            return []
        pages = [POLICIES[topic][0], *EXTRA_PAGES.get(topic, [])]
        return [Passage(page, self.pages[page], self.digest) for page in pages if self.pages.get(page)]

    def lookup(self, topic: str) -> tuple[str, str]:
        if topic not in POLICIES:
            return "I can only answer questions about the store and its products, orders and policies.", ""
        page, summary = POLICIES[topic]
        passages = self.retrieve(topic)
        content = self.pages.get(page)
        if len(passages) != 1 + len(EXTRA_PAGES.get(topic, [])):
            return "I couldn't verify this information in the store manual. Please contact our team.", ""
        # Source alignment check: summaries are explicitly tied to manual v2.1.
        # If a replacement source no longer includes the correct section, fail closed.
        anchors = {
            "address": "endereço", "hours": "Horário de Funcionamento", "contact": "WhatsApp",
            "payment": "Formas de Pagamento", "installments": "Regras de Parcelamento",
            "returns": "Direito de Arrependimento", "defects": "Trocas por Defeito",
            "exchange": "Trocas por Preferência", "shipping": "Frete e Entregas",
            "tracking": "Código de Rastreamento", "promotions": "Regras de Promoções",
            "warranty": "Garantia Legal", "privacy": "Privacidade e Proteção de Dados",
            "accessories": "instrumentos musicais",
            "complaints": "Reclamação",
        }
        if self.original_pdf:
            from .store import norm
            if norm(anchors[topic]) not in norm(content):
                return "The policy section could not be verified in this manual version. Please contact the store.", ""
        numbers = ', '.join(str(p.page) for p in passages)
        citation = f"[Store manual, p. {page}]" if len(passages) == 1 else f"[Store manual, pp. {numbers}]"
        return f"{summary} {citation}", f"store policy page(s) {numbers}; sha256 {self.digest[:12]}"
