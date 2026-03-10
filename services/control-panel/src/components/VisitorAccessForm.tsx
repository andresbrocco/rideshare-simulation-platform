import { useState } from 'react';
import { provisionVisitor, LambdaServiceError } from '../services/lambda';
import type { ProvisionVisitorResponse } from '../services/lambda';
import styles from './VisitorAccessForm.module.css';

// Intentionally simple — no RFC 5322 validation needed for this use case
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type FormState = 'idle' | 'loading' | 'success' | 'error';

interface SuccessData {
  email: string;
  emailSent: boolean;
}

export default function VisitorAccessForm() {
  const [formState, setFormState] = useState<FormState>('idle');
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successData, setSuccessData] = useState<SuccessData | null>(null);

  const emailValid = EMAIL_REGEX.test(email);
  const canSubmit = emailValid && consent;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canSubmit) return;

    setFormState('loading');
    try {
      const result: ProvisionVisitorResponse = await provisionVisitor(email);
      setSuccessData({
        email,
        emailSent: result.email_sent,
      });
      setFormState('success');
    } catch (err) {
      const message =
        err instanceof LambdaServiceError ? err.message : 'Something went wrong. Please try again.';
      setErrorMessage(message);
      setFormState('error');
    }
  };

  const handleTryAgain = () => {
    setFormState('idle');
    setErrorMessage('');
  };

  if (formState === 'success' && successData) {
    return (
      <div className={styles.container}>
        <div className={styles.successIcon}>&#10003;</div>
        <h3 className={styles.successTitle}>Check your email</h3>
        <p className={styles.successMessage}>
          Credentials have been sent to <strong>{successData.email}</strong>.
        </p>
        {!successData.emailSent && (
          <p className={styles.noteMessage}>
            Email delivery failed — check your spam folder or contact the author directly.
          </p>
        )}
        <p className={styles.noteMessage}>
          Your credentials will activate once the platform is deployed. Click &quot;Deploy&quot;
          below to get started.
        </p>
      </div>
    );
  }

  if (formState === 'error') {
    return (
      <div className={styles.container}>
        <div className={styles.errorIcon}>&#9888;</div>
        <h3 className={styles.errorTitle}>Request Failed</h3>
        <p className={styles.errorMessage}>{errorMessage}</p>
        <button className={styles.retryButton} onClick={handleTryAgain}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h3 className={styles.formTitle}>Request Visitor Access</h3>
      <p className={styles.formDescription}>
        Enter your email to receive temporary credentials and explore the live platform.
      </p>
      <form onSubmit={handleSubmit} noValidate>
        <div className={styles.fieldGroup}>
          <label htmlFor="visitor-email" className={styles.label}>
            Email address
          </label>
          <input
            id="visitor-email"
            type="email"
            className={styles.input}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            disabled={formState === 'loading'}
            autoComplete="email"
          />
        </div>
        <div className={styles.consentRow}>
          <input
            id="visitor-consent"
            type="checkbox"
            className={styles.checkbox}
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            disabled={formState === 'loading'}
          />
          <label htmlFor="visitor-consent" className={styles.consentLabel}>
            I understand that by submitting this form I will receive a welcome email with temporary
            credentials, my address will be stored for usage tracking, it will not be shared with
            third parties, and I can request deletion by replying to that email.
          </label>
        </div>
        <button
          type="submit"
          className={styles.submitButton}
          disabled={!canSubmit || formState === 'loading'}
        >
          {formState === 'loading' ? 'Sending...' : 'Request Access'}
        </button>
      </form>
    </div>
  );
}
