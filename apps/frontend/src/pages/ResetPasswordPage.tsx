import { useState, useEffect, FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Lock, Eye, EyeOff, Check } from "lucide-react";
import {
  Button,
  TextField,
  Card,
  CardContent,
  Box,
  Typography,
  Alert,
  IconButton,
  InputAdornment,
} from "@mui/material";
import apiClient from "@/lib/axios";

export const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  // Password strength indicators
  const passwordChecks = {
    length: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
  };

  const passwordStrength = Object.values(passwordChecks).filter(Boolean).length;

  useEffect(() => {
    if (!token) {
      setError("Invalid or missing reset token");
    }
  }, [token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!token) {
      setError("Invalid or missing reset token");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (passwordStrength < 4) {
      setError("Please meet all password requirements");
      return;
    }

    try {
      setError(null);
      setIsLoading(true);

      await apiClient.post("/auth/reset-password", {
        token,
        new_password: password,
      });

      setIsSuccess(true);

      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate("/login");
      }, 3000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to reset password. The link may have expired."
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
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
                  Password Reset Successful!
                </Typography>

                <Typography color="text.secondary" mb={3}>
                  Your password has been reset successfully. Redirecting to
                  login...
                </Typography>

                <Link to="/login" style={{ textDecoration: "none" }}>
                  <Button variant="contained" fullWidth>
                    Go to Sign In
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
            Reset Password
          </Typography>
          <Typography color="text.secondary" mt={1}>
            Enter your new password below
          </Typography>
        </Box>

        {/* Form Card */}
        <Card sx={{ boxShadow: 3 }}>
          <CardContent sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="bold" mb={0.5}>
              Create New Password
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Choose a strong password to secure your account
            </Typography>

            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                <Box>
                  <Typography variant="body2">{error}</Typography>
                  {error.includes("expired") && (
                    <Link
                      to="/forgot-password"
                      style={{
                        textDecoration: "underline",
                        fontSize: "0.875rem",
                      }}
                    >
                      Request a new reset link
                    </Link>
                  )}
                </Box>
              </Alert>
            )}

            <Box
              component="form"
              onSubmit={handleSubmit}
              sx={{ display: "flex", flexDirection: "column", gap: 2 }}
            >
              {/* New Password Field */}
              <Box>
                <TextField
                  id="password"
                  label="New Password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  autoFocus
                  disabled={!token}
                  fullWidth
                  InputProps={{
                    startAdornment: (
                      <Lock
                        style={{
                          marginRight: 8,
                          color: "#9e9e9e",
                          width: 20,
                          height: 20,
                        }}
                      />
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowPassword(!showPassword)}
                          edge="end"
                        >
                          {showPassword ? (
                            <EyeOff size={20} />
                          ) : (
                            <Eye size={20} />
                          )}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                {/* Password Strength Indicator */}
                {password && (
                  <Box sx={{ mt: 2 }}>
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
                            transition: "background-color 0.3s",
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
                        <Check style={{ width: 12, height: 12 }} />
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
                        <Check style={{ width: 12, height: 12 }} />
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
                        <Check style={{ width: 12, height: 12 }} />
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
                        <Check style={{ width: 12, height: 12 }} />
                        <span>Number</span>
                      </Box>
                    </Box>
                  </Box>
                )}
              </Box>

              {/* Confirm Password Field */}
              <TextField
                id="confirmPassword"
                label="Confirm New Password"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                disabled={!token}
                fullWidth
                InputProps={{
                  startAdornment: (
                    <Lock
                      style={{
                        marginRight: 8,
                        color: "#9e9e9e",
                        width: 20,
                        height: 20,
                      }}
                    />
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() =>
                          setShowConfirmPassword(!showConfirmPassword)
                        }
                        edge="end"
                      >
                        {showConfirmPassword ? (
                          <EyeOff size={20} />
                        ) : (
                          <Eye size={20} />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />

              {/* Submit Button */}
              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isLoading || !token}
                sx={{ mt: 1 }}
              >
                {isLoading ? "Resetting Password..." : "Reset Password"}
              </Button>
            </Box>

            <Box sx={{ mt: 3, textAlign: "center" }}>
              <Link
                to="/login"
                style={{
                  textDecoration: "none",
                  fontSize: "0.875rem",
                  color: "#666",
                }}
              >
                Back to Sign In
              </Link>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};
