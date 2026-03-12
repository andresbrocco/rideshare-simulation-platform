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
  const [errorMessage, setErrorMessage] = useState('');
  const [successData, setSuccessData] = useState<SuccessData | null>(null);

  const emailValid = EMAIL_REGEX.test(email);
  const canSubmit = emailValid;

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
      <h3 className={styles.formTitle}>Get your visitor access (free)</h3>
      <p className={styles.formDescription}>
        Receive your credentials and explore the live platform.
      </p>
      <form onSubmit={handleSubmit} noValidate>
        <div className={styles.fieldGroup}>
          <input
            id="visitor-email"
            type="email"
            className={styles.input}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            disabled={formState === 'loading'}
            autoComplete="email"
            aria-label="Email address"
          />
        </div>
        <button
          type="submit"
          className={styles.submitButton}
          disabled={!canSubmit || formState === 'loading'}
        >
          {formState === 'loading' ? 'Sending...' : 'Request Access'}
        </button>
        <p className={styles.consentNote}>
          By submitting, you'll receive credentials via email. Your address is stored for usage
          tracking, never shared, and deletable on request.
        </p>
      </form>
    </div>
  );
}
