import { InfoTooltip } from "./InfoTooltip";

type FieldLabelProps = {
  label: string;
  description?: string;
  recommendation?: string;
};

export function FieldLabel({
  label,
  description,
  recommendation
}: FieldLabelProps) {
  const hint = [description, recommendation].filter(Boolean).join("\n\n");

  return (
    <div className="field-heading">
      <strong>{label}</strong>
      {hint ? <InfoTooltip content={hint} label={`${label} hint`} /> : null}
    </div>
  );
}
