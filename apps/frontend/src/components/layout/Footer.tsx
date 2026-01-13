import { Link as RouterLink } from "react-router-dom";
import { Box, Typography, Link, Stack } from "@mui/material";

export const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <Box
      component="footer"
      sx={{
        mt: 8,
        py: 4,
        px: 6,
        backgroundColor: "transparent",
      }}
    >
      <Stack
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        alignItems="center"
        spacing={3}
      >
        {/* Left section */}
        <Typography
          variant="caption"
          sx={{
            color: "text.disabled",
            opacity: 0.5,
          }}
        >
          © {currentYear} Place Research. All rights reserved.
        </Typography>

        {/* Center section - Links */}
        <Stack direction="row" spacing={4}>
          <Link
            component={RouterLink}
            to="/privacy"
            underline="hover"
            sx={{
              color: "text.disabled",
              opacity: 0.5,
              fontSize: "0.75rem",
              "&:hover": {
                opacity: 0.8,
              },
            }}
          >
            Privacy Policy
          </Link>
          <Link
            component={RouterLink}
            to="/terms"
            underline="hover"
            sx={{
              color: "text.disabled",
              opacity: 0.5,
              fontSize: "0.75rem",
              "&:hover": {
                opacity: 0.8,
              },
            }}
          >
            Terms of Service
          </Link>
          <Link
            component={RouterLink}
            to="/contact"
            underline="hover"
            sx={{
              color: "text.disabled",
              opacity: 0.5,
              fontSize: "0.75rem",
              "&:hover": {
                opacity: 0.8,
              },
            }}
          >
            Contact
          </Link>
        </Stack>

        {/* Right section */}
        <Typography
          variant="caption"
          sx={{
            color: "text.disabled",
            opacity: 0.5,
          }}
        >
          Made with ❤️ for property research
        </Typography>
      </Stack>
    </Box>
  );
};
