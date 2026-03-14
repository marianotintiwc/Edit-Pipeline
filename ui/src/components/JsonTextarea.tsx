import { useEffect, useState } from "react";

interface JsonTextareaProps {
  label: string;
  value: Record<string, unknown> | null | undefined;
  onChange: (value: Record<string, unknown> | null) => void;
}

export function JsonTextarea({ label, value, onChange }: JsonTextareaProps) {
  const [text, setText] = useState(value ? JSON.stringify(value, null, 2) : "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(value ? JSON.stringify(value, null, 2) : "");
  }, [value]);

  const handleChange = (nextText: string) => {
    setText(nextText);

    if (!nextText.trim()) {
      setError(null);
      onChange(null);
      return;
    }

    try {
      const parsed = JSON.parse(nextText) as Record<string, unknown>;
      setError(null);
      onChange(parsed);
    } catch {
      setError("Enter valid JSON before leaving this field.");
    }
  };

  return (
    <label>
      {label}
      <textarea value={text} onChange={(event) => handleChange(event.target.value)} />
      {error ? <span>{error}</span> : null}
    </label>
  );
}
