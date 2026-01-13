import { AlertCircle } from "lucide-react";
import { Box, Typography, Button } from "@mui/material";
import { cn } from "@/lib/utils";

interface ErrorMessageProps {
  title?: string;
  message: string;
  retry?: () => void;
  className?: string;
}

export const ErrorMessage = ({
  title = "Error",
  message,
  retry,
  className,
}: ErrorMessageProps) => {
  return (
    <Box
      className={className}
      sx={{
        borderRadius: 2,
        border: 1,
        borderColor: "error.light",
        bgcolor: "error.lighter",
        p: 2,
      }}
    >
      <Box sx={{ display: "flex" }}>
        <AlertCircle size={20} style={{ color: "#f87171", flexShrink: 0 }} />
        <Box sx={{ ml: 1.5, flex: 1 }}>
          <Typography
            variant="body2"
            fontWeight="500"
            sx={{ color: "error.dark" }}
          >
            {title}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, color: "error.dark" }}>
            {message}
          </Typography>
          {retry && (
            <Button
              variant="text"
              onClick={retry}
              sx={{
                mt: 1.5,
                p: 0,
                minWidth: "auto",
                color: "error.dark",
                "&:hover": {
                  bgcolor: "transparent",
                  color: "error.main",
                },
              }}
            >
              Try again
            </Button>
          )}
        </Box>
      </Box>
    </Box>
  );
};
