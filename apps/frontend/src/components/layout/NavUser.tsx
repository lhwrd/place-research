import { useState } from "react";
import { LogOut, Settings, ChevronsUpDown } from "lucide-react";
import { Link } from "react-router-dom";
import {
  Avatar,
  Box,
  ListItemButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Typography,
  Divider,
} from "@mui/material";
import { useAuth } from "@/hooks/useAuth";

interface NavUserProps {
  user: {
    name: string;
    email: string;
    avatar: string;
  };
}

export function NavUser({ user }: NavUserProps) {
  const { logout } = useAuth();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  // Get initials from name
  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleClose();
    logout();
  };

  return (
    <Box>
      <ListItemButton
        onClick={handleClick}
        sx={{
          p: 2,
          "&:hover": { bgcolor: "action.hover" },
        }}
      >
        <ListItemIcon sx={{ minWidth: 40 }}>
          <Avatar
            src={user.avatar}
            alt={user.name}
            sx={{
              width: 32,
              height: 32,
              bgcolor: "grey.200",
              color: "text.primary",
            }}
          >
            {getInitials(user.name)}
          </Avatar>
        </ListItemIcon>
        <Box sx={{ flexGrow: 1, overflow: "hidden" }}>
          <Typography
            variant="body2"
            fontWeight="600"
            noWrap
            sx={{ lineHeight: 1.2 }}
          >
            {user.name}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ lineHeight: 1.2 }}
          >
            {user.email}
          </Typography>
        </Box>
        <ChevronsUpDown size={16} style={{ marginLeft: "auto" }} />
      </ListItemButton>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        PaperProps={{
          sx: { minWidth: 224 },
        }}
      >
        <Box sx={{ px: 2, py: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Avatar
              src={user.avatar}
              alt={user.name}
              sx={{
                width: 32,
                height: 32,
                bgcolor: "grey.200",
                color: "text.primary",
              }}
            >
              {getInitials(user.name)}
            </Avatar>
            <Box sx={{ overflow: "hidden" }}>
              <Typography variant="body2" fontWeight="600" noWrap>
                {user.name}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {user.email}
              </Typography>
            </Box>
          </Box>
        </Box>
        <Divider />
        <MenuItem component={Link} to="/preferences" onClick={handleClose}>
          <ListItemIcon sx={{ minWidth: 32 }}>
            <Settings size={16} />
          </ListItemIcon>
          Preferences
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleLogout} sx={{ color: "error.main" }}>
          <ListItemIcon sx={{ minWidth: 32, color: "error.main" }}>
            <LogOut size={16} />
          </ListItemIcon>
          Log out
        </MenuItem>
      </Menu>
    </Box>
  );
}
