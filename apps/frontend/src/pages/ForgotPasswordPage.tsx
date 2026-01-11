import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import { Mail, ArrowLeft, Check, AlertCircle, Info } from "lucide-react";
import {
  Button,
  TextField,
  Card,
  CardContent,
  Box,
  Typography,
  Alert,
  AlertTitle,
} from "@mui/material";
import apiClient from "@/lib/axios";

export const ForgotPasswordPage = () => {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address");
      return;
    }

    try {
      setIsLoading(true);

      await apiClient.post("/auth/request-password-reset", {
        email: email,
      });

      setIsSubmitted(true);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          "Failed to send reset email. Please try again."
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <Box
        sx={{
          minHeight: "100vh",
          background: "linear-gradient(135deg, #f5f5f5 0%, #e5e5e5 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          p: 2,
        }}
      >
        <Box sx={{ width: "100%", maxWidth: 450 }}>
          <Card sx={{ boxShadow: 3 }}>
            <CardContent sx={{ pt: 3 }}>
              <Box sx={{ textAlign: "center" }}>
                <Box
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 64,
                    height: 64,
                    bgcolor: "success.light",
                    borderRadius: "50%",
                    mb: 2,
                  }}
                >
                  <Check style={{ width: 32, height: 32, color: "#2e7d32" }} />
                </Box>

                <Typography
                  variant="h5"
                  fontWeight="bold"
                  color="text.primary"
                  mb={1}
                >
                  Check Your Email
                </Typography>

                <Typography color="text.secondary" mb={3}>
                  We've sent password reset instructions to{" "}
                  <Box
                    component="span"
                    fontWeight="medium"
                    color="text.primary"
                  >
                    {email}
                  </Box>
                </Typography>

                <Alert severity="info" sx={{ textAlign: "left", mb: 3 }}>
                  Didn't receive the email? Check your spam folder or{" "}
                  <Button
                    onClick={() => setIsSubmitted(false)}
                    sx={{ textDecoration: "underline", p: 0, minWidth: "auto" }}
                    color="inherit"
                  >
                    try again
                  </Button>
                </Alert>

                <Link to="/login" style={{ textDecoration: "none" }}>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<ArrowLeft size={16} />}
                  >
                    Back to Sign In
                  </Button>
                </Link>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #f5f5f5 0%, #e5e5e5 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 450 }}>
        {/* Logo/Header */}
        <Box sx={{ textAlign: "center", mb: 4 }}>
          <Box
            sx={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 64,
              height: 64,
              bgcolor: "primary.main",
              borderRadius: 2,
              mb: 2,
            }}
          >
            <Typography variant="h4" color="white" fontWeight="bold">
              P
            </Typography>
          </Box>
          <Typography variant="h4" fontWeight="bold" color="text.primary">
            Forgot Password?
          </Typography>
          <Typography color="text.secondary" mt={1}>
            Enter your email and we'll send you reset instructions
          </Typography>
        </Box>

        {/* Form Card */}
        <Card sx={{ boxShadow: 3 }}>
          <CardContent sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="bold" mb={0.5}>
              Reset Your Password
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              We'll email you instructions to reset your password
            </Typography>

            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
            )}

            <Box
              component="form"
              onSubmit={handleSubmit}
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              {/* Email Field */}
              <TextField
                id="email"
                label="Email Address"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
                fullWidth
                InputProps={{
                  startAdornment: (
                    <Mail
                      style={{
                        marginRight: 8,
                        color: "#9e9e9e",
                        width: 20,
                        height: 20,
                      }}
                    />
                  ),
                }}
              />

              {/* Submit Button */}
              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isLoading}
                sx={{ mt: 1 }}
              >
                {isLoading
                  ? "Sending Instructions..."
                  : "Send Reset Instructions"}
              </Button>
            </Box>

            <Box sx={{ mt: 3 }}>
              <Link to="/login" style={{ textDecoration: "none" }}>
                <Button
                  variant="text"
                  fullWidth
                  startIcon={<ArrowLeft size={16} />}
                >
                  Back to Sign In
                </Button>
              </Link>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};
