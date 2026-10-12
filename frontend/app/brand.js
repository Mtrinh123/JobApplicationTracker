// Brand mark: three board columns of different heights on the lavender tile
export default function Brand({ as: Tag = "span" }) {
  return (
    <Tag className="brand">
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        <rect width="20" height="20" rx="5" fill="var(--primary)" />
        <rect x="4.5" y="5" width="3" height="10" rx="1" fill="var(--on-primary)" />
        <rect x="8.5" y="5" width="3" height="7" rx="1" fill="var(--on-primary)" opacity="0.85" />
        <rect x="12.5" y="5" width="3" height="4" rx="1" fill="var(--on-primary)" opacity="0.7" />
      </svg>
      Job Tracker
    </Tag>
  );
}
