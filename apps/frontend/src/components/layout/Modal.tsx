import { ReactNode } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  SxProps,
  Theme,
} from "@mui/material";
import { X } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const sizeMap: Record<string, "sm" | "md" | "lg" | "xl"> = {
  sm: "sm",
  md: "md",
  lg: "lg",
  xl: "xl",
};

export const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  className,
}: ModalProps) => {
  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      maxWidth={sizeMap[size]}
      fullWidth
      PaperProps={{
        className,
      }}
    >
      {title && (
        <DialogTitle
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: 1,
            borderColor: "divider",
            p: 3,
          }}
        >
          {title}
          <IconButton
            edge="end"
            onClick={onClose}
            aria-label="close"
            sx={{ ml: 2 }}
          >
            <X size={20} />
          </IconButton>
        </DialogTitle>
      )}
      <DialogContent sx={{ p: 3 }}>{children}</DialogContent>
    </Dialog>
  );
};
