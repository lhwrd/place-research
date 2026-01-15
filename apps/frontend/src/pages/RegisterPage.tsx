import { useState, FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  Check,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import {
  Alert,
  TextField,
  Button,
  Card,
  CardContent,
  Box,
  Typography,
  Divider,
  Checkbox,
  FormControlLabel,
  IconButton,
  InputAdornment,
} from "@mui/material";
import axios from "axios";

export const RegisterPage = () => {
  const { register, isAuthenticated } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Password strength indicators
  const passwordChecks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
  };

  const passwordStrength = Object.values(passwordChecks).filter(Boolean).length;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (fullName.length < 2) {
      setError("Name must be at least 2 characters");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address");
      return;
    }

    if (passwordStrength < 4) {
      setError("Please meet all password requirements");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (!acceptTerms) {
      setError("You must accept the terms and conditions");
      return;
    }

    try {
      setIsLoading(true);
      await register({
        email: email,
        password: password,
        full_name: fullName,
      });
    } catch (err: unknown) {
      console.error("Registration error:", err);
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail ||
            "Registration failed. Please try again."
        );
      } else {
      setError("Registration failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
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
          \n{" "}
          <Box
            sx={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 64,
              height: 64,
              bgcolor: "#1f2937",
              borderRadius: 3,
              mb: 2,
            }}
          >
            <Typography
              variant="h4"
              sx={{ color: "white", fontWeight: "bold" }}
            >
              P
            </Typography>
          </Box>
          <Typography variant="h3" sx={{ fontWeight: "bold", mb: 1 }}>
            Create Account
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Start your property research journey today
          </Typography>
        </Box>

        {/* Registration Form Card */}
        <Card elevation={3}>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Sign Up
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Create your account to get started
            </Typography>

            {error && (
              <Alert
                severity="error"
                sx={{ mb: 3 }}
                icon={<AlertCircle size={20} />}
              >
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
                {/* Full Name Field */}
                <TextField
                  label="Full Name"
                  type="text"
                  placeholder="John Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  fullWidth
                  required
                  autoComplete="name"
                  autoFocus
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <User size={18} />
                      </InputAdornment>
                    ),
                  }}
                />

                {/* Email Field */}
                <TextField
                  label="Email Address"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  fullWidth
                  required
                  autoComplete="email"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Mail size={18} />
                      </InputAdornment>
                    ),
                  }}
                />

                {/* Password Field */}
                <Box>
                  <TextField
                    label="Password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    fullWidth
                    required
                    autoComplete="new-password"
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Lock size={18} />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            onClick={() => setShowPassword(!showPassword)}
                            edge="end"
                            size="small"
                          >
                            {showPassword ? (
                              <EyeOff size={18} />
                            ) : (
                              <Eye size={18} />
                            )}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />

                  {/* Password Strength Indicator */}
                  {password && (
                    <Box sx={{ mt: 1.5 }}>
                      <Box sx={{ display: "flex", gap: 0.5, mb: 1 }}>
                        {[1, 2, 3, 4].map((level) => (
                          <Box
                            key={level}
                            sx={{
                              height: 4,
                              flex: 1,
                              borderRadius: 1,
                              bgcolor:
                                level <= passwordStrength
                                  ? passwordStrength <= 2
                                    ? "error.main"
                                    : passwordStrength === 3
                                    ? "warning.main"
                                    : "success.main"
                                  : "grey.300",
                            }}
                          />
                        ))}
                      </Box>

                      <Box
                        sx={{
                          display: "grid",
                          gridTemplateColumns: "1fr 1fr",
                          gap: 1,
                          fontSize: "0.75rem",
                        }}
                      >
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: passwordChecks.length
                              ? "success.main"
                              : "text.disabled",
                          }}
                        >
                          <Check size={12} />
                          <span>8+ characters</span>
                        </Box>
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: passwordChecks.uppercase
                              ? "success.main"
                              : "text.disabled",
                          }}
                        >
                          <Check size={12} />
                          <span>Uppercase letter</span>
                        </Box>
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: passwordChecks.lowercase
                              ? "success.main"
                              : "text.disabled",
                          }}
                        >
                          <Check size={12} />
                          <span>Lowercase letter</span>
                        </Box>
                        <Box
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: passwordChecks.number
                              ? "success.main"
                              : "text.disabled",
                          }}
                        >
                          <Check size={12} />
                          <span>Number</span>
                        </Box>
                      </Box>
                    </Box>
                  )}
                </Box>

                {/* Confirm Password Field */}
                <TextField
                  label="Confirm Password"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  fullWidth
                  required
                  autoComplete="new-password"
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Lock size={18} />
                      </InputAdornment>
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() =>
                            setShowConfirmPassword(!showConfirmPassword)
                          }
                          edge="end"
                          size="small"
                        >
                          {showConfirmPassword ? (
                            <EyeOff size={18} />
                          ) : (
                            <Eye size={18} />
                          )}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                {/* Terms Checkbox */}
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={acceptTerms}
                      onChange={(e) => setAcceptTerms(e.target.checked)}
                    />
                  }
                  label={
                    <Typography variant="body2">
                      I agree to the{" "}
                      <Link to="/terms" style={{ textDecoration: "none" }}>
                        <Typography
                          component="span"
                          color="primary"
                          sx={{ "&:hover": { textDecoration: "underline" } }}
                        >
                          Terms of Service
                        </Typography>
                      </Link>{" "}
                      and{" "}
                      <Link to="/privacy" style={{ textDecoration: "none" }}>
                        <Typography
                          component="span"
                          color="primary"
                          sx={{ "&:hover": { textDecoration: "underline" } }}
                        >
                          Privacy Policy
                        </Typography>
                      </Link>
                    </Typography>
                  }
                />

                {/* Submit Button */}
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  disabled={isLoading}
                  size="large"
                >
                  {isLoading ? "Creating Account..." : "Create Account"}
                </Button>
              </Box>
            </form>

            <Divider sx={{ my: 3 }} />

            {/* Social Registration */}
            <Button
              variant="outlined"
              fullWidth
              onClick={() => alert("Google registration not implemented")}
              startIcon={
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
              }
            >
              Continue with Google
            </Button>

            {/* Sign In Link */}
            <Typography variant="body2" sx={{ mt: 3, textAlign: "center" }}>
              Already have an account?{" "}
              <Link to="/login" style={{ textDecoration: "none" }}>
                <Typography
                  component="span"
                  color="primary"
                  fontWeight={500}
                  sx={{ "&:hover": { textDecoration: "underline" } }}
                >
                  Sign in
                </Typography>
              </Link>
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};
