import toast, { Toaster } from 'react-hot-toast';

export { Toaster };

function parseError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'An unexpected error occurred';
}

export const showToast = {
  success: (message: string) => toast.success(message, { duration: 4000 }),
  error: (error: unknown) => toast.error(parseError(error), { duration: 6000 }),
  loading: (message: string) => toast.loading(message),
};
