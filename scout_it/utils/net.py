"""Network utility functions for checking internet connectivity."""

import socket
import time
from typing import Optional, Tuple


def check_internet_connection(timeout: int = 2, silent_on_success: bool = True) -> Tuple[bool, Optional[int]]:
    """Fast internet connectivity check using TCP socket connection.
    
    Uses DNS servers (port 53) for lightweight TCP connectivity test:
    - 1.1.1.1:53  (Cloudflare DNS)
    - 8.8.8.8:53  (Google DNS)
    - 9.9.9.9:53  (Quad9 DNS)
    
    This is faster than HTTP because it skips:
    - DNS lookup
    - TLS handshake
    - HTTP request/response
    
    Typical response time: <50ms
    
    Args:
        timeout: Connection timeout in seconds (default: 2s)
        silent_on_success: If True, don't print success message (default: True)
        
    Returns:
        Tuple of (is_connected: bool, latency_ms: Optional[int])
    """
    test_endpoints = [
        ("1.1.1.1", 53),  # Cloudflare DNS
        ("8.8.8.8", 53),  # Google DNS
        ("9.9.9.9", 53),  # Quad9 DNS
    ]
    
    for host, port in test_endpoints:
        try:
            start = time.perf_counter()
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            latency_ms = int((time.perf_counter() - start) * 1000)
            
            if not silent_on_success:
                print(f"[green]✓ Internet connection active ({latency_ms}ms)[/green]")
            
            return True, latency_ms
        except (socket.timeout, OSError):
            continue
    
    return False, None


def ensure_internet_connection(max_retries: int = 5, silent_on_success: bool = True) -> bool:
    """Ensure internet connection is available, with retry mechanism.
    
    Only displays output when connection fails. Silent on success.
    
    Retry delays: 3s, 5s, 10s, 15s, 20s (exponential backoff)
    
    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        silent_on_success: If True, don't print success message (default: True)
        
    Returns:
        True if connection established, False if all retries failed
    """
    # First attempt (silent check)
    is_connected, latency = check_internet_connection(timeout=2, silent_on_success=True)
    
    if is_connected:
        # Connection good - silent success
        return True
    
    # Connection failed - now show output
    print(f"[red]✗ No internet connection detected[/red]")
    print(f"[yellow]⏳ Attempting to establish connection...[/yellow]\n")
    
    # Retry with exponential backoff
    delays = [3, 5, 10, 15, 20]
    
    for attempt in range(1, max_retries + 1):
        print(f"[yellow]🔍 Checking internet connection (attempt {attempt}/{max_retries})...[/yellow]")
        
        is_connected, latency = check_internet_connection(timeout=2, silent_on_success=True)
        
        if is_connected:
            print(f"[green]✓ Internet connection restored! ({latency}ms)[/green]\n")
            return True
        
        print(f"[red]✗ Still no connection[/red]")
        
        if attempt < max_retries:
            # Get delay for this attempt
            delay = delays[attempt - 1] if attempt - 1 < len(delays) else delays[-1]
            print(f"[yellow]⏳ Retrying in {delay} seconds...[/yellow]")
            
            # Countdown display
            for remaining in range(delay, 0, -1):
                print(f"\r   Next retry in: {remaining}s ", end="", flush=True)
                time.sleep(1)
            
            print()  # New line after countdown
    
    # All retries failed
    print(f"\n[red]❌ FAILED: No internet connection after {max_retries} attempts[/red]")
    print(f"[yellow]Please check your network connection and try again.[/yellow]")
    print(f"[dim]Troubleshooting tips:[/dim]")
    print(f"  • Check if your Wi-Fi/Ethernet is connected")
    print(f"  • Try opening a website in your browser")
    print(f"  • Restart your router if needed")
    print(f"  • Check if a VPN is blocking the connection\n")
    
    return False
