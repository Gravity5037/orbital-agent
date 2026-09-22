//! Localhost-only HTTP client for talking to the out-of-process model
//! server.
//!
//! Hard constraints from the frozen spec, and how each is enforced here:
//! - Only 127.0.0.1 / [::1]: enforced by parsing the configured host as a
//!   literal IP address (never a hostname — no DNS resolution occurs at
//!   all) and rejecting anything that isn't loopback, both at client
//!   construction time and again by checking the peer address of the
//!   actual TCP connection before sending any request.
//! - No redirects: this client uses hyper's low-level `SendRequest`
//!   directly. There is no redirect-following logic anywhere in this file;
//!   a 3xx response is returned to the caller as an opaque, unfollowed
//!   response. Redirect-following would have to be added deliberately —
//!   it cannot happen by accident.
//! - Request/response size limits: enforced by `MAX_BODY_BYTES`, checked
//!   incrementally while streaming so an oversized response is aborted
//!   before it is fully buffered, not after.
//! - Model output has no authority: this module returns raw bytes to the
//!   caller. It does not parse tool calls itself and does not grant any
//!   permission. The complete response must finish streaming before the
//!   caller passes it to `schema::validate` — this module enforces that by
//!   only returning a value once the full (size-checked) body has been
//!   read, never a partial/streaming handle.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr};

use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::client::conn::http1;
use hyper::{Request, Response};
use thiserror::Error;
use tokio::net::TcpStream;

pub const MAX_REQUEST_BODY_BYTES: usize = 64 * 1024;
pub const MAX_RESPONSE_BODY_BYTES: usize = 1024 * 1024;

#[derive(Debug, Error)]
pub enum ModelClientError {
    #[error("host {0} is not a loopback address; only 127.0.0.1 and [::1] are permitted")]
    NotLoopback(IpAddr),
    #[error("configured host is not a literal IP address (DNS resolution is not permitted): {0}")]
    HostnameNotAllowed(String),
    #[error("connected peer address {0} is not loopback")]
    PeerNotLoopback(SocketAddr),
    #[error("request body exceeds MAX_REQUEST_BODY_BYTES ({MAX_REQUEST_BODY_BYTES})")]
    RequestTooLarge,
    #[error("response body exceeded MAX_RESPONSE_BODY_BYTES ({MAX_RESPONSE_BODY_BYTES}) before completing")]
    ResponseTooLarge,
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("http error: {0}")]
    Http(#[from] hyper::Error),
    #[error("http protocol error: {0}")]
    HttpProto(#[from] hyper::http::Error),
}

pub struct ModelClient {
    addr: SocketAddr,
    host_header: String,
}

impl ModelClient {
    /// `host` MUST be a literal IP string ("127.0.0.1" or "::1"), never a
    /// hostname. This is deliberate: resolving a hostname could be tricked
    /// (e.g. DNS rebinding) into pointing somewhere other than loopback.
    pub fn new(host: &str, port: u16) -> Result<Self, ModelClientError> {
        let ip: IpAddr = host
            .parse()
            .map_err(|_| ModelClientError::HostnameNotAllowed(host.to_string()))?;

        let is_loopback = match ip {
            IpAddr::V4(v4) => v4 == Ipv4Addr::LOCALHOST,
            IpAddr::V6(v6) => v6 == Ipv6Addr::LOCALHOST,
        };
        if !is_loopback {
            return Err(ModelClientError::NotLoopback(ip));
        }

        Ok(Self {
            addr: SocketAddr::new(ip, port),
            host_header: format!("{host}:{port}"),
        })
    }

    /// Send `body` as a POST to `path` and return the fully-buffered,
    /// size-checked response body. Returns before any tool-call parsing
    /// occurs — callers must pass the returned bytes to `schema::validate`
    /// themselves; this function never invokes it.
    pub async fn post(&self, path: &str, body: Vec<u8>) -> Result<Bytes, ModelClientError> {
        if body.len() > MAX_REQUEST_BODY_BYTES {
            return Err(ModelClientError::RequestTooLarge);
        }

        let stream = TcpStream::connect(self.addr).await?;

        // Defense in depth: re-check the actual peer address of the
        // established connection, not just the address we intended to
        // dial, is loopback before sending anything.
        let peer = stream.peer_addr()?;
        if !peer.ip().is_loopback() {
            return Err(ModelClientError::PeerNotLoopback(peer));
        }

        let io = hyper_util::rt::TokioIo::new(stream);
        let (mut sender, conn) = http1::handshake(io).await?;

        // Drive the connection in the background for the duration of this
        // single request/response.
        tokio::spawn(async move {
            let _ = conn.await;
        });

        let request = Request::builder()
            .method("POST")
            .uri(path)
            .header("host", &self.host_header)
            .header("content-type", "application/json")
            .header("content-length", body.len().to_string())
            .body(Full::new(Bytes::from(body)))?;

        let response: Response<Incoming> = sender.send_request(request).await?;

        // No redirect-following: a 3xx status is returned to the caller
        // as-is. There is no branch here that re-dispatches based on
        // status or a `location` header.
        let mut body_stream = response.into_body();
        let mut collected: Vec<u8> = Vec::new();

        while let Some(frame) = body_stream.frame().await {
            let frame = frame?;
            if let Some(chunk) = frame.data_ref() {
                if collected.len() + chunk.len() > MAX_RESPONSE_BODY_BYTES {
                    return Err(ModelClientError::ResponseTooLarge);
                }
                collected.extend_from_slice(chunk);
            }
        }

        Ok(Bytes::from(collected))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_ipv4_loopback() {
        assert!(ModelClient::new("127.0.0.1", 8080).is_ok());
    }

    #[test]
    fn accepts_ipv6_loopback() {
        assert!(ModelClient::new("::1", 8080).is_ok());
    }

    #[test]
    fn rejects_non_loopback_ip() {
        let result = ModelClient::new("192.168.1.5", 8080);
        assert!(matches!(result, Err(ModelClientError::NotLoopback(_))));
    }

    #[test]
    fn rejects_hostname_instead_of_literal_ip() {
        let result = ModelClient::new("localhost", 8080);
        assert!(matches!(result, Err(ModelClientError::HostnameNotAllowed(_))));
    }

    #[test]
    fn rejects_public_hostname() {
        let result = ModelClient::new("model.example.com", 8080);
        assert!(matches!(result, Err(ModelClientError::HostnameNotAllowed(_))));
    }
}