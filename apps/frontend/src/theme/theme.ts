import { createTheme } from '@mui/material/styles';

// Create a custom theme that works well with the existing design
export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#3b82f6', // Blue - similar to Tailwind blue-500
      light: '#60a5fa',
      dark: '#2563eb',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#8b5cf6', // Purple - similar to Tailwind purple-500
      light: '#a78bfa',
      dark: '#7c3aed',
      contrastText: '#ffffff',
    },
    error: {
      main: '#ef4444', // Red - similar to Tailwind red-500
      light: '#f87171',
      dark: '#dc2626',
    },
    warning: {
      main: '#f59e0b', // Amber - similar to Tailwind amber-500
      light: '#fbbf24',
      dark: '#d97706',
    },
    info: {
      main: '#0ea5e9', // Sky - similar to Tailwind sky-500
      light: '#38bdf8',
      dark: '#0284c7',
    },
    success: {
      main: '#10b981', // Emerald - similar to Tailwind emerald-500
      light: '#34d399',
      dark: '#059669',
    },
    background: {
      default: '#ffffff',
      paper: '#ffffff',
    },
    text: {
      primary: '#1f2937', // Gray-800
      secondary: '#6b7280', // Gray-500
    },
  },
  typography: {
    fontFamily: [
      'Inter Variable',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.25rem',
      fontWeight: 700,
      lineHeight: 1.2,
    },
    h2: {
      fontSize: '1.875rem',
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h3: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h4: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h5: {
      fontSize: '1.125rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
      lineHeight: 1.5,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.5,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    button: {
      textTransform: 'none', // Disable uppercase transformation
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 8, // Similar to Tailwind rounded-lg
  },
  spacing: 8, // 8px base unit (same as Tailwind)
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          padding: '8px 16px',
          fontSize: '0.875rem',
          fontWeight: 500,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
      },
      defaultProps: {
        disableElevation: true,
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
        size: 'small',
      },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 6,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
  },
});
