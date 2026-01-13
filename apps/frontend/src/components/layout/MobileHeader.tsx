import { AppBar, Toolbar, IconButton, Typography, Box } from "@mui/material";
import { Menu, Building2 } from "lucide-react";
import { Link } from "react-router-dom";

interface MobileHeaderProps {
  onDrawerToggle: () => void;
}

export const MobileHeader = ({ onDrawerToggle }: MobileHeaderProps) => {
  return (
    <AppBar
      position="static"
      color="default"
      elevation={0}
      sx={{
        display: { xs: "block", sm: "none" },
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Toolbar>
        <IconButton
          edge="start"
          onClick={onDrawerToggle}
          sx={{ mr: 2 }}
          aria-label="menu"
        >
          <Menu size={20} />
        </IconButton>
        <Box
          component={Link}
          to="/"
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            textDecoration: "none",
            color: "inherit",
          }}
        >
          <Building2 size={24} />
          <Typography variant="h6" fontWeight="600">
            Place Research
          </Typography>
        </Box>
      </Toolbar>
    </AppBar>
  );
};
