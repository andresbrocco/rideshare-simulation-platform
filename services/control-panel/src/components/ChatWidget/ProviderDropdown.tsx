import type { ProviderInfo } from '../../types/chat';

const DISPLAY_NAMES: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  deepseek: 'DeepSeek',
};

interface ProviderDropdownProps {
  providers: ProviderInfo[];
  selectedProvider: string;
  onProviderChange: (provider: string) => void;
  disabled: boolean;
}

export function ProviderDropdown({
  providers,
  selectedProvider,
  onProviderChange,
  disabled,
}: ProviderDropdownProps) {
  if (providers.length <= 1) {
    const label =
      providers.length === 1 ? (DISPLAY_NAMES[providers[0].name] ?? providers[0].name) : '';
    return <span className="chat-provider-label">{label}</span>;
  }

  return (
    <select
      className="chat-provider-select"
      value={selectedProvider}
      onChange={(e) => onProviderChange(e.target.value)}
      disabled={disabled}
      aria-label="Select LLM provider"
    >
      {providers.map((p) => (
        <option key={p.name} value={p.name}>
          {DISPLAY_NAMES[p.name] ?? p.name}
        </option>
      ))}
    </select>
  );
}
