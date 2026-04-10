type BrandLogoProps = {
  className?: string;
};

export function BrandLogo({ className = "" }: BrandLogoProps) {
  return (
    <span className={`brand-mark brand-mark-image ${className}`.trim()}>
      <img src="/mobguard-cat.png" alt="MobGuard" />
    </span>
  );
}
