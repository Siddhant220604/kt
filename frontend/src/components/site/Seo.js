import { Helmet } from 'react-helmet-async';

const SITE_NAME = 'Kiran Traders';
const DEFAULT_DESCRIPTION = 'Wholesale & Retail Packaging Essentials - Thermocol plates, carry bags, disposables & more. Trusted in Lucknow since 1996.';
const DEFAULT_IMAGE = 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=1200&q=80';

export default function Seo({ title, description, image, type = 'website', noindex = false }) {
  const fullTitle = title ? `${title} | ${SITE_NAME}` : `${SITE_NAME} - Wholesale Packaging Essentials | Lucknow, Since 1996`;
  const desc = description || DEFAULT_DESCRIPTION;
  const img = image || DEFAULT_IMAGE;
  const pageUrl = typeof window !== 'undefined' ? window.location.href : '';

  return (
    <Helmet>
      <title>{fullTitle}</title>
      <meta name="description" content={desc} />
      {noindex && <meta name="robots" content="noindex, nofollow" />}
      <link rel="canonical" href={pageUrl} />
      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={desc} />
      <meta property="og:image" content={img} />
      <meta property="og:url" content={pageUrl} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={desc} />
      <meta name="twitter:image" content={img} />
    </Helmet>
  );
}
