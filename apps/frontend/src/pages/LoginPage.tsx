import { useState, FormEvent } from "react";
import { Navigate, Link, useLocation } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import {
  Alert,
  TextField,
  Button,
  Card,
  CardContent,
  Box,
  Typography,
} from "@mui/material";
import axios from "axios";

export const LoginPage = () => {
  const { login, isAuthenticated } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({
        username: email,
        password: password,
      });
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail ||
            "Invalid email or password. Please try again."
        );
      } else {
        setError("Invalid email or password. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Redirect if already authenticated - back to where they came from or home
  if (isAuthenticated) {
    interface LocationState {
      from?: {
      pathname: string;
      };
    }
    const from = (location.state as LocationState)?.from?.pathname || "/";
    return <Navigate to={from} replace />;
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
            Welcome Back
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Sign in to continue your property search
          </Typography>
        </Box>

        {/* Error Alert */}
        {error && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            icon={<AlertCircle size={20} />}
          >
            {error}
          </Alert>
        )}

        {/* Login Form */}
        <Card elevation={3}>
          <CardContent sx={{ p: 4 }}>
            <form onSubmit={handleSubmit}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <TextField
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  fullWidth
                  required
                  autoComplete="email"
                  autoFocus
                />
                <TextField
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  fullWidth
                  required
                  autoComplete="current-password"
                />
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <Link
                    to="/forgot-password"
                    style={{ textDecoration: "none" }}
                  >
                    <Typography
                      variant="body2"
                      color="primary"
                      sx={{ "&:hover": { textDecoration: "underline" } }}
                    >
                      Forgot password?
                    </Typography>
                  </Link>
                </Box>
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  disabled={isLoading}
                  size="large"
                >
                  {isLoading ? "Signing in..." : "Sign In"}
                </Button>
                <Typography variant="body2" sx={{ textAlign: "center" }}>
                  Don't have an account?{" "}
                  <Link to="/register" style={{ textDecoration: "none" }}>
                    <Typography
                      component="span"
                      color="primary"
                      sx={{
                        fontWeight: 500,
                        "&:hover": { textDecoration: "underline" },
                      }}
                    >
                      Sign up
                    </Typography>
                  </Link>
                </Typography>
              </Box>
            </form>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};
