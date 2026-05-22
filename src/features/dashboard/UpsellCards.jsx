import { FileText, Users, ArrowUpRight } from 'lucide-react';

/**
 * Cards "ghost" de módulos no contratados. Empuja al usuario a
 * sumar capacidades del producto.
 *
 * Reglas de visibilidad:
 *  - `facturas-inteligentes`: si NO está en `modulosSet`.
 *  - `planilla-inteligente`: SIEMPRE (módulo aún no existe en
 *    producción; va con badge "Próximamente").
 *
 * El CTA "Conocer más" usa un `mailto:` como fallback hasta que
 * exista landing. Cambiarlo a futuro a WhatsApp o landing real.
 */

const CONTACT_EMAIL = 'contabilidad@cmejia.com.pe';

function ghostCardEmailLink(modulo) {
  const subject = `Activar módulo: ${modulo}`;
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}`;
}

export default function UpsellCards({ modulosSet, sistemaContable }) {
  const has = (mod) => modulosSet instanceof Set && modulosSet.has(mod);

  const cards = [];

  // Facturas Inteligentes — upsell solo si no está contratado
  if (!has('facturas-inteligentes')) {
    const sistemaUpper = sistemaContable ? String(sistemaContable).toUpperCase() : 'su sistema contable';
    cards.push({
      id: 'facturas-inteligentes',
      title: 'Facturas Inteligentes',
      badge: null,
      desc: `Procese facturas y boletas automáticamente. Yoko extrae los datos y arma el asiento contable directamente en ${sistemaUpper}.`,
      Icon: FileText,
      ctaHref: ghostCardEmailLink('Facturas Inteligentes'),
    });
  }

  // Planilla — siempre upsell ("Próximamente")
  cards.push({
    id: 'planilla-inteligente',
    title: 'Planilla',
    badge: 'Próximamente',
    desc: 'Procese planillas, detecte incidencias y genere boletas con IA. Solicite información para coordinar la activación.',
    Icon: Users,
    ctaHref: ghostCardEmailLink('Planilla'),
  });

  if (cards.length === 0) return null;

  return (
    <section className="erp-upsell" aria-label="Sumá más capacidades a Yoko">
      <h2 className="erp-upsell-title">Sumá más capacidades a Yoko</h2>
      <div className="erp-upsell-grid">
        {cards.map((c) => (
          <article key={c.id} className="erp-upsell-card">
            <div className="erp-upsell-card-top">
              <span className="erp-upsell-icon">
                <c.Icon size={18} />
              </span>
              {c.badge && <span className="erp-upsell-badge">{c.badge}</span>}
            </div>
            <h3 className="erp-upsell-card-title">{c.title}</h3>
            <p className="erp-upsell-card-desc">{c.desc}</p>
            <a className="erp-upsell-cta" href={c.ctaHref}>
              Conocer más
              <ArrowUpRight size={14} />
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}
