var myIP = null;
var hawsConn = null;
var hassBaseUrl = null;

/**
 * Main entrypoint / pre-initializer. Finds our IP address then calls
 * `doorPanelInit()`.
 */
function doorPanelPreInit() {
  hassBaseUrl = getHassWsUrl();
  $('#container').html('Connecting to ' + hassBaseUrl + ' ...');
  findIP(gotIp);
}

/**
 * Main initialization function, called after `gotIp()` found our IP address.
 */
function doorPanelInit() {
  $('#container').html('Connecting to ' + hassBaseUrl + ' ...<br />my IP: ' + myIP);
  HAWS.createConnection(hassBaseUrl).then(
    conn => {
      hawsConn = conn;
      conn.subscribeEvents(handleEvent);
    },
    err => {
      $('#container').html('Connection to ' + hassBaseUrl + ' failed; retry in 10s.<br />my IP: ' + myIP);
      window.setTimeout(doorPanelInit, 10000);
    }
  );
}

/** Callback on the HAWS connection; called for all events.
 *
 * Param is an Event object that includes old and new states.
 */
function handleEvent(e) {
  console.log('event: %o', e);
}

/**
 * Using the current URL, find the URL for the HASS WebSocket API.
 */
function getHassWsUrl() {
  return 'ws://' + window.location.hostname + ':' + window.location.port + '/api/websocket';
}

/**
 * Callback for `findIP()` when this host's IP is found.
 */
function gotIp(ip) {
  if (myIP != null) { return null; }
  myIP = ip;
  doorPanelInit();
}

/**
 * Finds the local machine's IP address. We send this in the Event that
 * goes to HASS and is processed by AppDaemon.
 *
 * Source: https://stackoverflow.com/a/32841164/211734
 */
function findIP(callback) {
  var myPeerConnection = window.RTCPeerConnection || window.mozRTCPeerConnection || window.webkitRTCPeerConnection; //compatibility for firefox and chrome
  var pc = new myPeerConnection({iceServers: []}),
    noop = function() {},
    localIPs = {},
    ipRegex = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/g,
    key;

  function ipIterate(ip) {
    if (!localIPs[ip]) callback(ip);
    localIPs[ip] = true;
    // ok, don't get any more...
    ipIterate = noop;
  }
  pc.createDataChannel(""); //create a bogus data channel
  pc.createOffer(function(sdp) {
    sdp.sdp.split('\n').forEach(function(line) {
      if (line.indexOf('candidate') < 0) return;
      line.match(ipRegex).forEach(ipIterate);
    });
    pc.setLocalDescription(sdp, noop, noop);
  }, noop); // create offer and set local description
  pc.onicecandidate = function(ice) { //listen for candidate events
    if (!ice || !ice.candidate || !ice.candidate.candidate || !ice.candidate.candidate.match(ipRegex)) return;
    ice.candidate.candidate.match(ipRegex).forEach(ipIterate);
  };
}