<?php
/**
 * Plugin Name: FBF BodyScan
 * Description: 360° video body-composition scanning. Accepts scan uploads from the FBF app (tier-priced: free on Recomp Protocols, $1 on Complete, $5 on Fitness/Nutrition), queues them for the GPU worker, stores results, and deletes raw video after processing.
 * Version: 1.1.1
 * Author: Forged by Freedom
 * License: GPL-2.0+
 */

defined( 'ABSPATH' ) || exit;

class FBF_BodyScan {

	const NS          = 'fbf/v1';
	const DB_VERSION  = '1.0';
	const TOKEN_META  = 'fbf_app_tokens'; // shared with FBF App Bridge
	const CREDITS     = 'fbf_scan_credits';
	const UPLOADS_META = 'fbf_scan_uploads';

	/** Hard ceiling on a finished scan video. */
	const MAX_VIDEO_BYTES = 209715200; // 200 MB
	/** Chunk size advertised to clients. Stays under a 2M upload_max_filesize. */
	const CHUNK_BYTES = 1048576; // 1 MB
	/** Abandoned multipart uploads are swept after this long. */
	const UPLOAD_TTL = 86400; // 24 h

	/* What this plugin needs the PHP runtime to allow. */
	const REQ_UPLOAD_MAX = '256M';
	const REQ_POST_MAX   = '272M';
	const REQ_MEMORY     = '256M';
	const REQ_EXEC_TIME  = '600';
	const REQ_INPUT_TIME = '600';

	public static function init() {
		register_activation_hook( __FILE__, array( __CLASS__, 'activate' ) );
		add_action( 'plugins_loaded', array( __CLASS__, 'maybe_upgrade' ) );
		add_action( 'rest_api_init', array( __CLASS__, 'routes' ) );
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_init', array( __CLASS__, 'admin_boot' ) );
		add_action( 'admin_post_fbf_bodyscan_settings', array( __CLASS__, 'save_settings' ) );
		add_action( 'admin_post_fbf_bodyscan_credit', array( __CLASS__, 'grant_credit' ) );
		add_action( 'admin_post_fbf_bodyscan_fixini', array( __CLASS__, 'fix_ini_action' ) );
		add_action( 'fbf_bodyscan_sweep', array( __CLASS__, 'sweep_uploads' ) );
	}

	private static function table() {
		global $wpdb;
		return $wpdb->prefix . 'fbf_bodyscans';
	}

	public static function activate() {
		self::create_table();
		update_option( 'fbf_bodyscan_db_version', self::DB_VERSION );
		if ( ! get_option( 'fbf_bodyscan_worker_key' ) ) {
			update_option( 'fbf_bodyscan_worker_key', wp_generate_password( 40, false, false ) );
		}
		self::storage_dir(); // create protected dir now
		self::write_user_ini();
		if ( ! wp_next_scheduled( 'fbf_bodyscan_sweep' ) ) {
			wp_schedule_event( time() + 3600, 'daily', 'fbf_bodyscan_sweep' );
		}
	}

	public static function maybe_upgrade() {
		if ( get_option( 'fbf_bodyscan_db_version' ) !== self::DB_VERSION ) {
			self::create_table();
			update_option( 'fbf_bodyscan_db_version', self::DB_VERSION );
		}
		if ( ! wp_next_scheduled( 'fbf_bodyscan_sweep' ) ) {
			wp_schedule_event( time() + 3600, 'daily', 'fbf_bodyscan_sweep' );
		}
	}

	/**
	 * Keep the PHP upload ceiling correct without anyone having to remember.
	 * Runs at most once a day, in admin only, so it never costs a request.
	 */
	public static function admin_boot() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		if ( get_transient( 'fbf_bodyscan_ini_checked' ) ) {
			return;
		}
		set_transient( 'fbf_bodyscan_ini_checked', 1, DAY_IN_SECONDS );
		if ( ! self::php_limits_ok() ) {
			self::write_user_ini();
		}
	}

	private static function create_table() {
		global $wpdb;
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		dbDelta( 'CREATE TABLE ' . self::table() . " (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			user_id BIGINT UNSIGNED NOT NULL,
			status VARCHAR(20) NOT NULL DEFAULT 'queued',
			intake LONGTEXT NULL,
			result LONGTEXT NULL,
			report MEDIUMTEXT NULL,
			fail_reason TEXT NULL,
			video_path VARCHAR(255) NOT NULL DEFAULT '',
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			PRIMARY KEY (id),
			KEY user_idx (user_id),
			KEY status_idx (status)
		) " . $wpdb->get_charset_collate() . ';' );
	}

	public static function table_exists() {
		global $wpdb;
		$t = self::table();
		return $t === $wpdb->get_var( $wpdb->prepare( 'SHOW TABLES LIKE %s', $t ) );
	}

	private static function storage_dir() {
		$up  = wp_upload_dir();
		$dir = trailingslashit( $up['basedir'] ) . 'fbf-bodyscan';
		if ( ! is_dir( $dir ) ) {
			wp_mkdir_p( $dir );
		}
		// Block direct web access to raw videos.
		if ( ! file_exists( $dir . '/.htaccess' ) ) {
			file_put_contents( $dir . '/.htaccess', "Deny from all\n" );
		}
		if ( ! file_exists( $dir . '/index.php' ) ) {
			file_put_contents( $dir . '/index.php', "<?php // silence\n" );
		}
		return $dir;
	}

	private static function parts_dir( $upload_id ) {
		$dir = self::storage_dir() . '/parts';
		if ( ! is_dir( $dir ) ) {
			wp_mkdir_p( $dir );
		}
		return $dir . '/' . $upload_id;
	}

	/* ----------------------------------------------------------- php ini */

	/** "8M" -> 8388608. Returns 0 for unlimited/unset. */
	public static function bytes( $val ) {
		$val = trim( (string) $val );
		if ( '' === $val || '-1' === $val ) {
			return 0;
		}
		$unit = strtolower( substr( $val, -1 ) );
		$num  = (float) $val;
		switch ( $unit ) {
			case 'g':
				$num *= 1024;
				// no break
			case 'm':
				$num *= 1024;
				// no break
			case 'k':
				$num *= 1024;
		}
		return (int) $num;
	}

	public static function php_limits() {
		return array(
			'upload_max_filesize' => (string) ini_get( 'upload_max_filesize' ),
			'post_max_size'       => (string) ini_get( 'post_max_size' ),
			'memory_limit'        => (string) ini_get( 'memory_limit' ),
			'max_execution_time'  => (string) ini_get( 'max_execution_time' ),
			'upload_bytes'        => self::bytes( ini_get( 'upload_max_filesize' ) ),
			'post_bytes'          => self::bytes( ini_get( 'post_max_size' ) ),
		);
	}

	/** True when a whole-file 200 MB submit can physically get through. */
	public static function php_limits_ok() {
		$l = self::php_limits();
		return $l['upload_bytes'] >= self::MAX_VIDEO_BYTES && $l['post_bytes'] > self::MAX_VIDEO_BYTES;
	}

	/** True when at least one CHUNK_BYTES part can get through. */
	public static function chunking_ok() {
		$l    = self::php_limits();
		$need = self::CHUNK_BYTES + 65536; // chunk plus form overhead
		return $l['upload_bytes'] >= self::CHUNK_BYTES && $l['post_bytes'] >= $need;
	}

	public static function user_ini_path() {
		$name = (string) ini_get( 'user_ini.filename' );
		if ( '' === $name ) {
			$name = '.user.ini';
		}
		return rtrim( ABSPATH, '/\\' ) . DIRECTORY_SEPARATOR . $name;
	}

	private static function managed_ini_block() {
		return "; BEGIN FBF BodyScan — managed automatically, edits inside this block are overwritten\n"
			. 'upload_max_filesize = ' . self::REQ_UPLOAD_MAX . "\n"
			. 'post_max_size = ' . self::REQ_POST_MAX . "\n"
			. 'memory_limit = ' . self::REQ_MEMORY . "\n"
			. 'max_execution_time = ' . self::REQ_EXEC_TIME . "\n"
			. 'max_input_time = ' . self::REQ_INPUT_TIME . "\n"
			. "; END FBF BodyScan\n";
	}

	/**
	 * Merge our block into the document-root .user.ini, preserving anything
	 * else that is already in there.
	 *
	 * @return array{ok:bool,path:string,note:string}
	 */
	public static function write_user_ini() {
		$path = self::user_ini_path();
		$dir  = dirname( $path );
		if ( ! is_writable( $dir ) && ! file_exists( $path ) ) {
			return array( 'ok' => false, 'path' => $path, 'note' => 'Document root is not writable by PHP.' );
		}
		if ( file_exists( $path ) && ! is_writable( $path ) ) {
			return array( 'ok' => false, 'path' => $path, 'note' => 'Existing file is not writable by PHP.' );
		}

		$existing = file_exists( $path ) ? (string) file_get_contents( $path ) : '';
		$stripped = preg_replace(
			'/;\s*BEGIN FBF BodyScan.*?;\s*END FBF BodyScan\s*/s',
			'',
			$existing
		);
		if ( null === $stripped ) {
			$stripped = $existing;
		}
		$new = rtrim( $stripped );
		$new = ( '' === $new ) ? self::managed_ini_block() : $new . "\n\n" . self::managed_ini_block();

		if ( $new === $existing ) {
			return array( 'ok' => true, 'path' => $path, 'note' => 'Already up to date.' );
		}
		if ( '' !== $existing && ! file_exists( $path . '.fbf-bak' ) ) {
			@file_put_contents( $path . '.fbf-bak', $existing );
		}
		$wrote = @file_put_contents( $path, $new );
		if ( false === $wrote ) {
			return array( 'ok' => false, 'path' => $path, 'note' => 'Write failed.' );
		}
		@chmod( $path, 0644 );
		update_option( 'fbf_bodyscan_ini_written', time() );
		return array(
			'ok'   => true,
			'path' => $path,
			'note' => 'Written. PHP caches .user.ini for up to ' . (int) ini_get( 'user_ini.cache_ttl' ) . 's, so new limits appear shortly.',
		);
	}

	/* ------------------------------------------- .htaccess limits fallback */

	public static function htaccess_path() {
		return rtrim( ABSPATH, '/\\' ) . DIRECTORY_SEPARATOR . '.htaccess';
	}

	/**
	 * True when PHP is actually honouring per-directory ini files at all.
	 * If user_ini.filename is empty the .user.ini we write is dead weight and
	 * the only remaining lever is .htaccess (LiteSpeed / mod_php) or cPanel.
	 */
	public static function user_ini_enabled() {
		return '' !== trim( (string) ini_get( 'user_ini.filename' ) );
	}

	private static function managed_htaccess_block() {
		return "# BEGIN FBF BodyScan\n"
			. 'php_value upload_max_filesize ' . self::REQ_UPLOAD_MAX . "\n"
			. 'php_value post_max_size ' . self::REQ_POST_MAX . "\n"
			. 'php_value memory_limit ' . self::REQ_MEMORY . "\n"
			. 'php_value max_execution_time ' . self::REQ_EXEC_TIME . "\n"
			. 'php_value max_input_time ' . self::REQ_INPUT_TIME . "\n"
			. "# END FBF BodyScan\n";
	}

	private static function strip_htaccess_block( $s ) {
		$out = preg_replace( '/#\s*BEGIN FBF BodyScan.*?#\s*END FBF BodyScan\s*/s', '', (string) $s );
		return ( null === $out ) ? (string) $s : $out;
	}

	/** Loopback check: does the public site still answer without a 5xx? */
	private static function site_responds() {
		$r = wp_remote_get(
			add_query_arg( 'fbf_probe', (string) time(), home_url( '/' ) ),
			array( 'timeout' => 15, 'sslverify' => false, 'redirection' => 2 )
		);
		if ( is_wp_error( $r ) ) {
			return false;
		}
		return ( (int) wp_remote_retrieve_response_code( $r ) < 500 );
	}

	/**
	 * Some hosts ignore .user.ini entirely. On those, php_value directives in
	 * the document-root .htaccess are the working lever — but on a plain
	 * PHP-FPM/CGI Apache they throw a 500 for the whole site. So: back up,
	 * write, immediately re-fetch the homepage, and revert on the spot if the
	 * server rejected it. Worst case the site is unhappy for about a second.
	 *
	 * @return array{ok:bool,note:string}
	 */
	public static function write_htaccess() {
		$path = self::htaccess_path();
		$dir  = dirname( $path );
		if ( file_exists( $path ) ? ! is_writable( $path ) : ! is_writable( $dir ) ) {
			return array( 'ok' => false, 'note' => '.htaccess is not writable by PHP, so the limits could not be forced there.' );
		}
		if ( ! self::site_responds() ) {
			return array( 'ok' => false, 'note' => 'Skipped the .htaccess fallback: the site did not answer its own loopback request beforehand, so the safety rollback could not be trusted.' );
		}

		$existing = file_exists( $path ) ? (string) file_get_contents( $path ) : '';
		if ( '' !== $existing && ! file_exists( $path . '.fbf-bak' ) ) {
			@file_put_contents( $path . '.fbf-bak', $existing );
		}
		$stripped = rtrim( self::strip_htaccess_block( $existing ) );
		$new      = ( '' === $stripped ) ? self::managed_htaccess_block() : $stripped . "\n\n" . self::managed_htaccess_block();

		if ( false === @file_put_contents( $path, $new ) ) {
			return array( 'ok' => false, 'note' => 'Writing .htaccess failed.' );
		}

		if ( self::site_responds() ) {
			update_option( 'fbf_bodyscan_htaccess_ok', time(), false );
			return array( 'ok' => true, 'note' => 'Upload limits also written to .htaccess and the site still loads normally.' );
		}

		// Server rejected php_value — put everything back exactly as it was.
		if ( '' === $existing ) {
			@unlink( $path );
		} else {
			@file_put_contents( $path, $existing );
		}
		update_option( 'fbf_bodyscan_htaccess_ok', 0, false );
		return array(
			'ok'   => false,
			'note' => 'This server rejects php_value in .htaccess, so the change was reverted automatically and the site is back to normal. Raise upload_max_filesize / post_max_size in cPanel > MultiPHP INI Editor; scans keep working over the chunked upload path in the meantime.',
		);
	}

	/** Remove our .htaccess block (used when limits are fine without it). */
	public static function clear_htaccess() {
		$path = self::htaccess_path();
		if ( ! file_exists( $path ) || ! is_writable( $path ) ) {
			return false;
		}
		$existing = (string) file_get_contents( $path );
		$stripped = self::strip_htaccess_block( $existing );
		if ( $stripped === $existing ) {
			return false;
		}
		return false !== @file_put_contents( $path, rtrim( $stripped ) . "\n" );
	}

	/* ------------------------------------------------------------ app auth */

	private static function bearer( $request ) {
		$h = $request->get_header( 'authorization' );
		return ( $h && 0 === stripos( $h, 'Bearer ' ) ) ? trim( substr( $h, 7 ) ) : '';
	}

	/** Same token scheme as FBF App Bridge (shared user meta). */
	private static function user_from_token( $token ) {
		if ( ! $token ) {
			return null;
		}
		$hash  = wp_hash( $token );
		$users = get_users( array(
			'meta_key' => self::TOKEN_META,
			'meta_compare' => 'EXISTS',
			'fields'   => 'ID',
			'number'   => 500,
		) );
		foreach ( $users as $uid ) {
			$tokens = get_user_meta( $uid, self::TOKEN_META, true );
			if ( is_array( $tokens ) && isset( $tokens[ $hash ] ) && $tokens[ $hash ] > time() ) {
				return (int) $uid;
			}
		}
		return null;
	}

	public static function app_auth( $request ) {
		$uid = self::user_from_token( self::bearer( $request ) );
		if ( ! $uid ) {
			return new WP_Error( 'fbf_unauthorized', 'Invalid or expired token.', array( 'status' => 401 ) );
		}
		$request->set_param( '_fbf_user_id', $uid );
		return true;
	}

	public static function worker_auth( $request ) {
		$key = (string) $request->get_header( 'x-fbf-worker' );
		$ok  = $key && hash_equals( (string) get_option( 'fbf_bodyscan_worker_key' ), $key );
		if ( $ok ) {
			update_option( 'fbf_bodyscan_worker_seen', time(), false );
			return true;
		}
		return new WP_Error( 'fbf_forbidden', 'Bad worker key.', array( 'status' => 403 ) );
	}

	public static function admin_auth() {
		return current_user_can( 'manage_options' )
			? true
			: new WP_Error( 'fbf_forbidden', 'Admins only.', array( 'status' => 403 ) );
	}

	/* ------------------------------------------------------------- pricing */

	/** Returns array( 'free'|'paid'|'denied', price_usd, payment_url ). */
	public static function pricing_for( $uid ) {
		$user = get_user_by( 'id', $uid );
		if ( $user && ( user_can( $user, 'manage_options' ) || in_array( 'coach', (array) $user->roles, true ) ) ) {
			return array( 'free', 0, '' );
		}
		$level_id = 0;
		if ( function_exists( 'pmpro_getMembershipLevelForUser' ) ) {
			$lvl      = pmpro_getMembershipLevelForUser( $uid );
			$level_id = $lvl ? (int) $lvl->id : 0;
		}
		if ( in_array( $level_id, array( 5, 6 ), true ) ) { // Recomp Protocols
			return array( 'free', 0, '' );
		}
		if ( 4 === $level_id ) { // Complete Coaching
			return array( 'paid', 1, (string) get_option( 'fbf_bodyscan_pay_url_1', '' ) );
		}
		if ( in_array( $level_id, array( 2, 3 ), true ) ) { // Fitness / Nutrition
			return array( 'paid', 5, (string) get_option( 'fbf_bodyscan_pay_url_5', '' ) );
		}
		return array( 'denied', 0, '' ); // no active membership
	}

	/* -------------------------------------------------------------- routes */

	public static function routes() {
		register_rest_route( self::NS, '/bodyscan/submit', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'submit' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/mine', array(
			'methods'  => 'GET',
			'callback' => array( __CLASS__, 'mine' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/limits', array(
			'methods'  => 'GET',
			'callback' => array( __CLASS__, 'limits' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/upload/begin', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'upload_begin' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/upload/part', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'upload_part' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/upload/abort', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'upload_abort' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/report/(?P<id>\d+)', array(
			'methods'  => 'GET',
			'callback' => array( __CLASS__, 'report' ),
			'permission_callback' => array( __CLASS__, 'app_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/queue', array(
			'methods'  => 'GET',
			'callback' => array( __CLASS__, 'queue' ),
			'permission_callback' => array( __CLASS__, 'worker_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/video/(?P<id>\d+)', array(
			'methods'  => 'GET',
			'callback' => array( __CLASS__, 'video' ),
			'permission_callback' => array( __CLASS__, 'worker_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/result/(?P<id>\d+)', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'result' ),
			'permission_callback' => array( __CLASS__, 'worker_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/fail/(?P<id>\d+)', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'fail' ),
			'permission_callback' => array( __CLASS__, 'worker_auth' ),
		) );
		register_rest_route( self::NS, '/bodyscan/selftest', array(
			'methods'  => 'POST',
			'callback' => array( __CLASS__, 'selftest' ),
			'permission_callback' => array( __CLASS__, 'admin_auth' ),
		) );
	}

	/* ------------------------------------------------- upload diagnostics */

	/**
	 * PHP throws away the whole request body when it exceeds post_max_size:
	 * $_POST and $_FILES arrive empty and the handler cannot tell that a file
	 * was ever attached. Detect that precisely instead of blaming the client.
	 */
	private static function body_was_dropped() {
		$len = isset( $_SERVER['CONTENT_LENGTH'] ) ? (int) $_SERVER['CONTENT_LENGTH'] : 0;
		$max = self::bytes( ini_get( 'post_max_size' ) );
		return ( $len > 0 && $max > 0 && $len > $max && empty( $_FILES ) && empty( $_POST ) );
	}

	private static function upload_error_text( $code ) {
		switch ( (int) $code ) {
			case UPLOAD_ERR_INI_SIZE:
				return 'The server rejected the file: it is larger than PHP upload_max_filesize ('
					. ini_get( 'upload_max_filesize' ) . ').';
			case UPLOAD_ERR_FORM_SIZE:
				return 'The file exceeded the form MAX_FILE_SIZE limit.';
			case UPLOAD_ERR_PARTIAL:
				return 'The upload was cut off before it finished — connection dropped.';
			case UPLOAD_ERR_NO_FILE:
				return 'No file arrived.';
			case UPLOAD_ERR_NO_TMP_DIR:
				return 'The server has no temp directory for uploads.';
			case UPLOAD_ERR_CANT_WRITE:
				return 'The server could not write the upload to disk.';
			case UPLOAD_ERR_EXTENSION:
				return 'A PHP extension blocked the upload.';
		}
		return 'Unknown upload error (' . (int) $code . ').';
	}

	private static function too_big_error() {
		$l = self::php_limits();
		return new WP_Error(
			'fbf_server_limit',
			'The video was blocked by the server before it reached the app: this server currently accepts '
			. $l['upload_max_filesize'] . ' per file and ' . $l['post_max_size']
			. ' per request. Upload it in chunks (POST /bodyscan/upload/begin) or raise the PHP limits.',
			array(
				'status'              => 413,
				'upload_max_filesize' => $l['upload_max_filesize'],
				'post_max_size'       => $l['post_max_size'],
				'chunk_size'          => self::CHUNK_BYTES,
				'chunked_upload'      => rest_url( self::NS . '/bodyscan/upload/begin' ),
			)
		);
	}

	public static function limits( $request ) {
		$l = self::php_limits();
		return array(
			'max_video_bytes'     => self::MAX_VIDEO_BYTES,
			'chunk_size'          => self::CHUNK_BYTES,
			'upload_max_filesize' => $l['upload_max_filesize'],
			'post_max_size'       => $l['post_max_size'],
			'whole_file_ok'       => self::php_limits_ok(),
			'chunked_ok'          => self::chunking_ok(),
			// Clients should chunk whenever a single POST cannot carry the file.
			'recommended'         => self::php_limits_ok() ? 'whole' : 'chunked',
		);
	}

	/* -------------------------------------------------- chunked uploading */

	private static function get_uploads_meta( $uid ) {
		$m = get_user_meta( $uid, self::UPLOADS_META, true );
		return is_array( $m ) ? $m : array();
	}

	public static function upload_begin( $request ) {
		$uid = (int) $request->get_param( '_fbf_user_id' );

		$name  = sanitize_file_name( (string) $request->get_param( 'filename' ) );
		$size  = (int) $request->get_param( 'size' );
		$check = wp_check_filetype( $name, array(
			'mp4' => 'video/mp4',
			'mov' => 'video/quicktime',
			'm4v' => 'video/x-m4v',
		) );
		if ( empty( $check['ext'] ) ) {
			return new WP_Error( 'fbf_bad_type', 'Video must be .mp4 or .mov.', array( 'status' => 400 ) );
		}
		if ( $size > self::MAX_VIDEO_BYTES ) {
			return new WP_Error( 'fbf_too_big', 'Video too large (200 MB max). Record at 1080p, one slow turn.', array( 'status' => 400 ) );
		}

		$upload_id = wp_generate_password( 32, false, false );
		$dir       = self::parts_dir( $upload_id );
		if ( ! wp_mkdir_p( $dir ) ) {
			return new WP_Error( 'fbf_store_fail', 'Could not open an upload slot on the server.', array( 'status' => 500 ) );
		}

		$meta                 = self::get_uploads_meta( $uid );
		$meta[ $upload_id ]   = array(
			'ext'     => $check['ext'],
			'size'    => $size,
			'started' => time(),
			'parts'   => 0,
			'bytes'   => 0,
		);
		update_user_meta( $uid, self::UPLOADS_META, $meta );

		return array(
			'upload_id'  => $upload_id,
			'chunk_size' => self::CHUNK_BYTES,
			'part_url'   => rest_url( self::NS . '/bodyscan/upload/part' ),
			'expires_in' => self::UPLOAD_TTL,
		);
	}

	public static function upload_part( $request ) {
		$uid = (int) $request->get_param( '_fbf_user_id' );

		if ( self::body_was_dropped() ) {
			return self::too_big_error();
		}

		$upload_id = (string) $request->get_param( 'upload_id' );
		if ( ! preg_match( '/^[A-Za-z0-9]{32}$/', $upload_id ) ) {
			return new WP_Error( 'fbf_bad_upload', 'Unknown upload_id.', array( 'status' => 400 ) );
		}
		$meta = self::get_uploads_meta( $uid );
		if ( ! isset( $meta[ $upload_id ] ) ) {
			return new WP_Error( 'fbf_bad_upload', 'Unknown or expired upload_id — call /bodyscan/upload/begin again.', array( 'status' => 400 ) );
		}

		$seq = (int) $request->get_param( 'seq' );
		if ( $seq < 0 || $seq > 4095 ) {
			return new WP_Error( 'fbf_bad_upload', 'Bad chunk sequence.', array( 'status' => 400 ) );
		}

		$files = $request->get_file_params();
		$part  = $files['chunk'] ?? null;
		if ( ! $part ) {
			return new WP_Error( 'fbf_no_chunk', 'Attach the chunk as the "chunk" file field.', array( 'status' => 400 ) );
		}
		if ( ! empty( $part['error'] ) ) {
			return new WP_Error( 'fbf_chunk_error', self::upload_error_text( $part['error'] ), array( 'status' => 400 ) );
		}

		$dir = self::parts_dir( $upload_id );
		if ( ! is_dir( $dir ) ) {
			return new WP_Error( 'fbf_bad_upload', 'Upload slot is gone — start over.', array( 'status' => 400 ) );
		}

		$dest = $dir . '/part-' . str_pad( (string) $seq, 5, '0', STR_PAD_LEFT );
		if ( ! @move_uploaded_file( $part['tmp_name'], $dest ) ) {
			return new WP_Error( 'fbf_store_fail', 'Could not store that chunk — retry it.', array( 'status' => 500 ) );
		}

		$bytes = 0;
		$count = 0;
		foreach ( (array) glob( $dir . '/part-*' ) as $f ) {
			$bytes += (int) filesize( $f );
			$count++;
		}
		if ( $bytes > self::MAX_VIDEO_BYTES ) {
			self::rm_parts( $upload_id );
			unset( $meta[ $upload_id ] );
			update_user_meta( $uid, self::UPLOADS_META, $meta );
			return new WP_Error( 'fbf_too_big', 'Video too large (200 MB max).', array( 'status' => 400 ) );
		}

		$meta[ $upload_id ]['parts'] = $count;
		$meta[ $upload_id ]['bytes'] = $bytes;
		update_user_meta( $uid, self::UPLOADS_META, $meta );

		return array( 'ok' => true, 'seq' => $seq, 'parts' => $count, 'bytes' => $bytes );
	}

	public static function upload_abort( $request ) {
		$uid       = (int) $request->get_param( '_fbf_user_id' );
		$upload_id = (string) $request->get_param( 'upload_id' );
		$meta      = self::get_uploads_meta( $uid );
		if ( isset( $meta[ $upload_id ] ) ) {
			self::rm_parts( $upload_id );
			unset( $meta[ $upload_id ] );
			update_user_meta( $uid, self::UPLOADS_META, $meta );
		}
		return array( 'ok' => true );
	}

	private static function rm_parts( $upload_id ) {
		if ( ! preg_match( '/^[A-Za-z0-9]{32}$/', (string) $upload_id ) ) {
			return;
		}
		$dir = self::parts_dir( $upload_id );
		if ( ! is_dir( $dir ) ) {
			return;
		}
		foreach ( (array) glob( $dir . '/part-*' ) as $f ) {
			@unlink( $f );
		}
		@rmdir( $dir );
	}

	/** Stream the parts into one file. Never loads the video into memory. */
	private static function assemble( $upload_id, $dest ) {
		$dir   = self::parts_dir( $upload_id );
		$parts = (array) glob( $dir . '/part-*' );
		if ( ! $parts ) {
			return false;
		}
		sort( $parts, SORT_STRING );
		$out = @fopen( $dest, 'wb' );
		if ( ! $out ) {
			return false;
		}
		foreach ( $parts as $p ) {
			$in = @fopen( $p, 'rb' );
			if ( ! $in ) {
				fclose( $out );
				@unlink( $dest );
				return false;
			}
			stream_copy_to_stream( $in, $out );
			fclose( $in );
		}
		fclose( $out );
		return true;
	}

	/** Drop multipart uploads nobody finished. */
	public static function sweep_uploads() {
		$root = self::storage_dir() . '/parts';
		if ( ! is_dir( $root ) ) {
			return;
		}
		$cutoff = time() - self::UPLOAD_TTL;
		foreach ( (array) glob( $root . '/*', GLOB_ONLYDIR ) as $dir ) {
			if ( (int) filemtime( $dir ) < $cutoff ) {
				foreach ( (array) glob( $dir . '/part-*' ) as $f ) {
					@unlink( $f );
				}
				@rmdir( $dir );
			}
		}
	}

	/* ---------------------------------------------------------- app routes */

	public static function submit( $request ) {
		global $wpdb;
		$uid = (int) $request->get_param( '_fbf_user_id' );

		// The single most common real-world failure: the request never made it
		// through PHP intact. Say so, precisely, instead of "attach a video".
		if ( self::body_was_dropped() ) {
			return self::too_big_error();
		}
		if ( ! self::table_exists() ) {
			self::create_table();
			if ( ! self::table_exists() ) {
				return new WP_Error( 'fbf_db_missing', 'Scan storage table is missing on the server.', array( 'status' => 500 ) );
			}
		}

		list( $mode, $price, $pay_url ) = self::pricing_for( $uid );
		if ( 'denied' === $mode ) {
			return new WP_Error( 'fbf_no_membership',
				'BodyScan requires an active FBF coaching membership.',
				array( 'status' => 403 ) );
		}
		if ( 'paid' === $mode ) {
			$credits = (int) get_user_meta( $uid, self::CREDITS, true );
			if ( $credits < 1 ) {
				return new WP_Error( 'fbf_payment_required', sprintf(
					'This scan costs $%d on your plan. Pay at the link, then your coach will add a scan credit to your account.',
					$price
				), array( 'status' => 402, 'price_usd' => $price, 'payment_url' => $pay_url ) );
			}
			// NOTE: the credit is NOT spent here. It is spent only once the
			// video is safely on disk, so a failed upload never costs a client
			// a paid scan.
		}

		$files     = $request->get_file_params();
		$upload_id = (string) $request->get_param( 'upload_id' );
		$source    = '';
		$ext       = '';

		if ( $upload_id ) {
			$meta = self::get_uploads_meta( $uid );
			if ( ! isset( $meta[ $upload_id ] ) ) {
				return new WP_Error( 'fbf_bad_upload', 'Unknown or expired upload_id.', array( 'status' => 400 ) );
			}
			$ext    = $meta[ $upload_id ]['ext'];
			$source = 'chunked';
		} elseif ( ! empty( $files['video'] ) && ! empty( $files['video']['error'] ) ) {
			$code = (int) $files['video']['error'];
			if ( UPLOAD_ERR_INI_SIZE === $code ) {
				return self::too_big_error();
			}
			return new WP_Error( 'fbf_upload_error', self::upload_error_text( $code ), array( 'status' => 400 ) );
		} elseif ( ! empty( $files['video']['tmp_name'] ) ) {
			$size = (int) $files['video']['size'];
			if ( $size > self::MAX_VIDEO_BYTES ) {
				return new WP_Error( 'fbf_too_big', 'Video too large (200 MB max). Record at 1080p, one slow turn.', array( 'status' => 400 ) );
			}
			$check = wp_check_filetype( $files['video']['name'], array(
				'mp4' => 'video/mp4',
				'mov' => 'video/quicktime',
				'm4v' => 'video/x-m4v',
			) );
			if ( empty( $check['ext'] ) ) {
				return new WP_Error( 'fbf_bad_type', 'Video must be .mp4 or .mov.', array( 'status' => 400 ) );
			}
			$ext    = $check['ext'];
			$source = 'whole';
		} else {
			return new WP_Error( 'fbf_no_video',
				'Attach the scan video as the "video" file field, or finish a chunked upload and pass upload_id.',
				array( 'status' => 400 ) );
		}

		$intake = array();
		foreach ( array( 'sex', 'age', 'height_in', 'height_cm', 'weight_lb', 'weight_kg',
			'neck_in', 'chest_in', 'waist_in', 'hips_in', 'thigh_in', 'arm_in',
			'neck_cm', 'chest_cm', 'waist_cm', 'hips_cm', 'thigh_cm', 'arm_cm' ) as $f ) {
			$v = $request->get_param( $f );
			if ( null !== $v && '' !== $v ) {
				$intake[ $f ] = sanitize_text_field( (string) $v );
			}
		}
		if ( empty( $intake['sex'] ) || ( empty( $intake['height_in'] ) && empty( $intake['height_cm'] ) ) ) {
			return new WP_Error( 'fbf_missing_fields', 'sex and height are required.', array( 'status' => 400 ) );
		}

		$inserted = $wpdb->insert( self::table(), array(
			'user_id'    => $uid,
			'status'     => 'queued',
			'intake'     => wp_json_encode( $intake ),
			'created_at' => current_time( 'mysql', true ),
			'updated_at' => current_time( 'mysql', true ),
		) );
		$id = (int) $wpdb->insert_id;
		if ( ! $inserted || ! $id ) {
			return new WP_Error( 'fbf_db_write', 'Could not record the scan — try again.', array( 'status' => 500 ) );
		}

		$dest = self::storage_dir() . '/scan-' . $id . '.' . $ext;
		$ok   = ( 'chunked' === $source )
			? self::assemble( $upload_id, $dest )
			: (bool) @move_uploaded_file( $files['video']['tmp_name'], $dest );

		if ( ! $ok || ! file_exists( $dest ) || filesize( $dest ) < 1024 ) {
			@unlink( $dest );
			$wpdb->delete( self::table(), array( 'id' => $id ) );
			return new WP_Error( 'fbf_store_fail', 'Could not store the upload — try again.', array( 'status' => 500 ) );
		}

		if ( 'chunked' === $source ) {
			self::rm_parts( $upload_id );
			$meta = self::get_uploads_meta( $uid );
			unset( $meta[ $upload_id ] );
			update_user_meta( $uid, self::UPLOADS_META, $meta );
		}

		// Video is on disk. Now, and only now, charge the credit.
		if ( 'paid' === $mode ) {
			$credits = (int) get_user_meta( $uid, self::CREDITS, true );
			update_user_meta( $uid, self::CREDITS, max( 0, $credits - 1 ) );
		}

		$wpdb->update( self::table(), array( 'video_path' => $dest ), array( 'id' => $id ) );

		return array(
			'id'      => $id,
			'status'  => 'queued',
			'bytes'   => (int) filesize( $dest ),
			'message' => 'Scan received. Processing usually takes a few minutes — check back shortly.',
		);
	}

	public static function mine( $request ) {
		global $wpdb;
		$uid  = (int) $request->get_param( '_fbf_user_id' );
		$rows = $wpdb->get_results( $wpdb->prepare(
			'SELECT id, status, result, fail_reason, created_at FROM ' . self::table() .
			' WHERE user_id = %d ORDER BY id DESC LIMIT 50', $uid ) );
		$out = array();
		foreach ( (array) $rows as $r ) {
			$res   = $r->result ? json_decode( $r->result, true ) : null;
			$out[] = array(
				'id'           => (int) $r->id,
				'status'       => $r->status,
				'created_at'   => $r->created_at,
				'bf_percent'   => $res['bf_percent'] ?? null,
				'bf_low'       => $res['bf_low'] ?? null,
				'bf_high'      => $res['bf_high'] ?? null,
				'category'     => $res['category'] ?? null,
				'lean_mass_kg' => $res['lean_mass_kg'] ?? null,
				'measurements' => $res['measurements'] ?? null,
				'warnings'     => $res['warnings'] ?? array(),
				'fail_reason'  => $r->fail_reason,
			);
		}
		list( $mode, $price, $pay_url ) = self::pricing_for( $uid );
		return array(
			'scans'   => $out,
			'pricing' => array(
				'mode'        => $mode,
				'price_usd'   => $price,
				'payment_url' => $pay_url,
				'credits'     => (int) get_user_meta( $uid, self::CREDITS, true ),
			),
			'upload'  => array(
				'chunk_size'  => self::CHUNK_BYTES,
				'recommended' => self::php_limits_ok() ? 'whole' : 'chunked',
			),
		);
	}

	public static function report( $request ) {
		global $wpdb;
		$uid = (int) $request->get_param( '_fbf_user_id' );
		$id  = (int) $request['id'];
		$row = $wpdb->get_row( $wpdb->prepare(
			'SELECT user_id, report FROM ' . self::table() . ' WHERE id = %d', $id ) );
		$is_coach = user_can( $uid, 'manage_options' ) || user_can( $uid, 'fbf_coach' );
		if ( ! $row || ( (int) $row->user_id !== $uid && ! $is_coach ) ) {
			return new WP_Error( 'fbf_not_found', 'Scan not found.', array( 'status' => 404 ) );
		}
		if ( ! $row->report ) {
			return new WP_Error( 'fbf_not_ready', 'Report not ready yet.', array( 'status' => 409 ) );
		}
		$resp = new WP_REST_Response( $row->report );
		$resp->header( 'Content-Type', 'text/html; charset=utf-8' );
		return $resp;
	}

	/* ------------------------------------------------------- worker routes */

	public static function queue( $request ) {
		global $wpdb;
		// atomic claim: only one worker row flips queued -> processing
		$claimed = 0;
		$row     = null;
		for ( $try = 0; $try < 3 && ! $claimed; $try++ ) {
			$row = $wpdb->get_row( 'SELECT id FROM ' . self::table() .
				" WHERE status = 'queued' ORDER BY id ASC LIMIT 1" );
			if ( ! $row ) {
				return new WP_REST_Response( null, 204 );
			}
			$claimed = $wpdb->query( $wpdb->prepare(
				'UPDATE ' . self::table() .
				" SET status = 'processing', updated_at = %s WHERE id = %d AND status = 'queued'",
				current_time( 'mysql', true ), $row->id ) );
		}
		if ( ! $claimed || ! $row ) {
			return new WP_REST_Response( null, 204 );
		}
		$scan   = $wpdb->get_row( $wpdb->prepare(
			'SELECT * FROM ' . self::table() . ' WHERE id = %d', $row->id ) );
		$intake = $scan->intake ? json_decode( $scan->intake, true ) : array();
		$user   = get_user_by( 'id', $scan->user_id );

		// previous completed scan for the trend line
		$prev_row = $wpdb->get_row( $wpdb->prepare(
			'SELECT result, created_at FROM ' . self::table() .
			" WHERE user_id = %d AND status = 'complete' AND id < %d ORDER BY id DESC LIMIT 1",
			$scan->user_id, $scan->id ) );
		$prev = null;
		if ( $prev_row && $prev_row->result ) {
			$pr   = json_decode( $prev_row->result, true );
			$prev = array(
				'bf_percent' => $pr['bf_percent'] ?? null,
				'date'       => substr( (string) $prev_row->created_at, 0, 10 ),
			);
		}

		return array_merge( (array) $intake, array(
			'id'      => (int) $scan->id,
			'user_id' => (int) $scan->user_id,
			'name'    => $user ? $user->display_name : 'Client',
			'prev'    => $prev,
		) );
	}

	public static function video( $request ) {
		global $wpdb;
		$id  = (int) $request['id'];
		$row = $wpdb->get_row( $wpdb->prepare(
			'SELECT video_path FROM ' . self::table() . ' WHERE id = %d', $id ) );
		if ( ! $row || ! $row->video_path || ! file_exists( $row->video_path ) ) {
			return new WP_Error( 'fbf_no_file', 'Video missing.', array( 'status' => 404 ) );
		}
		$ext   = strtolower( (string) pathinfo( $row->video_path, PATHINFO_EXTENSION ) );
		$types = array( 'mp4' => 'video/mp4', 'm4v' => 'video/x-m4v', 'mov' => 'video/quicktime' );
		// stream directly and exit — REST response objects buffer in memory
		nocache_headers();
		while ( ob_get_level() > 0 ) {
			ob_end_clean();
		}
		header( 'Content-Type: ' . ( $types[ $ext ] ?? 'application/octet-stream' ) );
		header( 'Content-Length: ' . filesize( $row->video_path ) );
		readfile( $row->video_path );
		exit;
	}

	private static function delete_video( $row ) {
		global $wpdb;
		if ( $row && $row->video_path && file_exists( $row->video_path ) ) {
			@unlink( $row->video_path );
		}
		$wpdb->update( self::table(), array( 'video_path' => '' ), array( 'id' => $row->id ) );
	}

	public static function result( $request ) {
		global $wpdb;
		$id  = (int) $request['id'];
		$row = $wpdb->get_row( $wpdb->prepare(
			'SELECT * FROM ' . self::table() . ' WHERE id = %d', $id ) );
		if ( ! $row ) {
			return new WP_Error( 'fbf_not_found', 'Scan not found.', array( 'status' => 404 ) );
		}
		$data   = $request->get_json_params();
		$report = (string) ( $data['report_html'] ?? '' );
		unset( $data['report_html'] );

		$wpdb->update( self::table(), array(
			'status'     => 'complete',
			'result'     => wp_json_encode( $data ),
			'report'     => $report,
			'updated_at' => current_time( 'mysql', true ),
		), array( 'id' => $id ) );
		self::delete_video( $row ); // process-and-delete policy

		// let the client know
		$user = get_user_by( 'id', $row->user_id );
		if ( $user ) {
			$bf = $data['bf_percent'] ?? '?';
			wp_mail( $user->user_email, 'Your FBF BodyScan results are ready',
				"Hi {$user->display_name},\n\nYour body scan is done: estimated body fat {$bf}%.\n"
				. "Open the FBF app to see your full report, measurements, and trend.\n\n"
				. "Questions? Reply here or email forgedbyfreedom@proton.me.\n\n"
				. '— Forged by Freedom' );
		}
		return array( 'ok' => true );
	}

	public static function fail( $request ) {
		global $wpdb;
		$id  = (int) $request['id'];
		$row = $wpdb->get_row( $wpdb->prepare(
			'SELECT * FROM ' . self::table() . ' WHERE id = %d', $id ) );
		if ( ! $row ) {
			return new WP_Error( 'fbf_not_found', 'Scan not found.', array( 'status' => 404 ) );
		}
		$data = $request->get_json_params();
		$wpdb->update( self::table(), array(
			'status'      => 'failed',
			'fail_reason' => sanitize_textarea_field( (string) ( $data['reason'] ?? 'Processing failed.' ) ),
			'updated_at'  => current_time( 'mysql', true ),
		), array( 'id' => $id ) );
		self::delete_video( $row ); // delete even on failure

		// failed paid scans give the credit back
		list( $mode ) = self::pricing_for( $row->user_id );
		if ( 'paid' === $mode ) {
			$c = (int) get_user_meta( $row->user_id, self::CREDITS, true );
			update_user_meta( $row->user_id, self::CREDITS, $c + 1 );
		}
		return array( 'ok' => true );
	}

	/* --------------------------------------------------------- self-test */

	/**
	 * Pushes a real file through the real storage path so "is upload working?"
	 * is a button, not a guess. Admin-only; writes and deletes a probe file.
	 */
	public static function selftest( $request ) {
		$out = array(
			'php'            => self::php_limits(),
			'whole_file_ok'  => self::php_limits_ok(),
			'chunked_ok'     => self::chunking_ok(),
			'table_exists'   => self::table_exists(),
			'storage_dir'    => self::storage_dir(),
			'storage_write'  => is_writable( self::storage_dir() ),
			'user_ini'       => self::user_ini_path(),
			'user_ini_write' => file_exists( self::user_ini_path() )
				? is_writable( self::user_ini_path() )
				: is_writable( dirname( self::user_ini_path() ) ),
			'body_dropped'   => self::body_was_dropped(),
			'content_length' => isset( $_SERVER['CONTENT_LENGTH'] ) ? (int) $_SERVER['CONTENT_LENGTH'] : 0,
		);

		if ( $out['body_dropped'] ) {
			$out['probe'] = array( 'ok' => false, 'why' => 'PHP discarded the request body: it exceeded post_max_size.' );
			return $out;
		}

		$files = $request->get_file_params();
		if ( empty( $files['probe'] ) ) {
			$out['probe'] = array( 'ok' => false, 'why' => 'No probe file was sent.' );
			return $out;
		}
		if ( ! empty( $files['probe']['error'] ) ) {
			$out['probe'] = array(
				'ok'  => false,
				'why' => self::upload_error_text( $files['probe']['error'] ),
			);
			return $out;
		}

		$dest = self::storage_dir() . '/selftest-' . wp_generate_password( 8, false, false ) . '.bin';
		$ok   = @move_uploaded_file( $files['probe']['tmp_name'], $dest );
		$size = $ok && file_exists( $dest ) ? (int) filesize( $dest ) : 0;
		if ( $ok ) {
			@unlink( $dest );
		}
		$out['probe'] = array(
			'ok'       => (bool) $ok,
			'received' => $size,
			'claimed'  => (int) $files['probe']['size'],
			'why'      => $ok ? 'Stored and removed successfully.' : 'move_uploaded_file() failed.',
		);
		return $out;
	}

	/* --------------------------------------------------------------- admin */

	public static function menu() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		add_menu_page( 'FBF BodyScan', 'FBF BodyScan', 'manage_options',
			'fbf-bodyscan', array( __CLASS__, 'render_admin' ), 'dashicons-visibility', 59 );
	}

	private static function ok_bad( $ok, $good, $bad ) {
		return $ok
			? '<span style="color:#1a7f37;font-weight:600">' . esc_html( $good ) . '</span>'
			: '<span style="color:#b32d2e;font-weight:600">' . esc_html( $bad ) . '</span>';
	}

	public static function render_admin() {
		global $wpdb;
		$key   = get_option( 'fbf_bodyscan_worker_key' );
		$rows  = self::table_exists()
			? $wpdb->get_results( 'SELECT * FROM ' . self::table() . ' ORDER BY id DESC LIMIT 100' )
			: array();
		$users = get_users( array( 'fields' => array( 'ID', 'display_name' ), 'number' => 500, 'orderby' => 'display_name' ) );
		$l     = self::php_limits();
		$seen  = (int) get_option( 'fbf_bodyscan_worker_seen', 0 );

		echo '<div class="wrap"><h1>FBF BodyScan</h1>';
		if ( isset( $_GET['saved'] ) ) { echo '<div class="notice notice-success"><p>Settings saved.</p></div>'; }
		if ( isset( $_GET['credited'] ) ) { echo '<div class="notice notice-success"><p>Scan credit added.</p></div>'; }
		if ( isset( $_GET['ini'] ) ) {
			$note = get_transient( 'fbf_bodyscan_ini_note' );
			echo '<div class="notice notice-info"><p>' . esc_html( $note ? $note : 'PHP limits re-applied.' ) . '</p></div>';
		}

		/* ---- diagnostics -------------------------------------------------- */
		echo '<h2>System check</h2><table class="widefat striped" style="max-width:900px"><tbody>';

		printf(
			'<tr><td style="width:280px"><strong>Upload ceiling (per file)</strong></td><td>%s &nbsp; %s</td></tr>',
			esc_html( $l['upload_max_filesize'] ),
			self::ok_bad(
				$l['upload_bytes'] >= self::MAX_VIDEO_BYTES,
				'OK',
				'TOO LOW — scan videos are blocked before they reach WordPress'
			)
		);
		printf(
			'<tr><td><strong>Request ceiling (whole POST)</strong></td><td>%s &nbsp; %s</td></tr>',
			esc_html( $l['post_max_size'] ),
			self::ok_bad( $l['post_bytes'] > self::MAX_VIDEO_BYTES, 'OK', 'TOO LOW' )
		);
		printf(
			'<tr><td><strong>Chunked upload path</strong></td><td>%s</td></tr>',
			self::ok_bad( self::chunking_ok(), 'Working — scans upload in ' . size_format( self::CHUNK_BYTES ) . ' pieces', 'Blocked' )
		);
		printf(
			'<tr><td><strong>PHP memory / max exec</strong></td><td>%s / %ss</td></tr>',
			esc_html( $l['memory_limit'] ),
			esc_html( $l['max_execution_time'] )
		);
		printf(
			'<tr><td><strong>Scan storage</strong></td><td><code>%s</code> &nbsp; %s</td></tr>',
			esc_html( self::storage_dir() ),
			self::ok_bad( is_writable( self::storage_dir() ), 'Writable', 'NOT WRITABLE' )
		);
		printf(
			'<tr><td><strong>Database table</strong></td><td><code>%s</code> &nbsp; %s</td></tr>',
			esc_html( self::table() ),
			self::ok_bad( self::table_exists(), 'Present', 'MISSING' )
		);
		printf(
			'<tr><td><strong>PHP limits file</strong></td><td><code>%s</code> &nbsp; %s</td></tr>',
			esc_html( self::user_ini_path() ),
			self::ok_bad(
				file_exists( self::user_ini_path() ),
				'Present',
				'Not written yet'
			)
		);
		printf(
			'<tr><td><strong>Per-directory PHP ini</strong></td><td>%s &nbsp; %s</td></tr>',
			esc_html( self::user_ini_enabled() ? (string) ini_get( 'user_ini.filename' ) . ' (cached ' . (int) ini_get( 'user_ini.cache_ttl' ) . 's)' : 'disabled' ),
			self::ok_bad(
				self::user_ini_enabled(),
				'Honoured by PHP',
				'IGNORED by this server — .user.ini cannot change the limits here'
			)
		);
		printf(
			'<tr><td><strong>.htaccess limits</strong></td><td><code>%s</code> &nbsp; %s</td></tr>',
			esc_html( self::htaccess_path() ),
			(int) get_option( 'fbf_bodyscan_htaccess_ok', 0 )
				? '<span style="color:#00782a;font-weight:600">Applied and verified</span>'
				: '<span style="color:#646970">Not applied</span>'
		);
		printf(
			'<tr><td><strong>PHP SAPI</strong></td><td>%s</td></tr>',
			esc_html( php_sapi_name() )
		);
		printf(
			'<tr><td><strong>GPU worker (3090)</strong></td><td>%s</td></tr>',
			$seen
				? self::ok_bad(
					( time() - $seen ) < 900,
					'Polling — last seen ' . human_time_diff( $seen ) . ' ago',
					'STALE — last seen ' . human_time_diff( $seen ) . ' ago; queued scans will not process'
				)
				: '<span style="color:#b32d2e;font-weight:600">NEVER SEEN — the worker has not polled this site</span>'
		);
		echo '</tbody></table>';

		echo '<p><form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="display:inline">';
		wp_nonce_field( 'fbf_bodyscan_fixini' );
		echo '<input type="hidden" name="action" value="fbf_bodyscan_fixini" />';
		submit_button( 'Force PHP upload limits (auto-reverts if refused)', 'secondary', 'submit', false );
		echo '</form> <button type="button" class="button button-primary" id="fbf-selftest">Run upload self-test (12 MB)</button></p>';
		echo '<pre id="fbf-selftest-out" style="background:#fff;border:1px solid #ccd0d4;padding:12px;max-width:900px;white-space:pre-wrap;display:none"></pre>';

		/* ---- settings ----------------------------------------------------- */
		echo '<h2>Settings</h2><form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="background:#fff;border:1px solid #ccd0d4;padding:16px;max-width:820px">';
		wp_nonce_field( 'fbf_bodyscan_settings' );
		echo '<input type="hidden" name="action" value="fbf_bodyscan_settings" />';
		echo '<table class="form-table"><tbody>';
		echo '<tr><th>Worker API key</th><td><code>' . esc_html( $key ) . '</code><br /><em>Paste into config.yaml on the 3090 machine.</em></td></tr>';
		echo '<tr><th>$1 payment link (Complete)</th><td><input class="regular-text" name="pay1" value="' . esc_attr( get_option( 'fbf_bodyscan_pay_url_1', '' ) ) . '" placeholder="https://buy.stripe.com/..." /></td></tr>';
		echo '<tr><th>$5 payment link (Fitness/Nutrition)</th><td><input class="regular-text" name="pay5" value="' . esc_attr( get_option( 'fbf_bodyscan_pay_url_5', '' ) ) . '" placeholder="https://buy.stripe.com/..." /></td></tr>';
		echo '</tbody></table>';
		submit_button( 'Save settings' );
		echo '</form>';

		/* ---- credits ------------------------------------------------------ */
		echo '<h2>Add a scan credit (after a client pays)</h2><form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" style="background:#fff;border:1px solid #ccd0d4;padding:16px;max-width:820px">';
		wp_nonce_field( 'fbf_bodyscan_credit' );
		echo '<input type="hidden" name="action" value="fbf_bodyscan_credit" /><select name="user_id">';
		foreach ( $users as $u ) {
			echo '<option value="' . (int) $u->ID . '">' . esc_html( $u->display_name ) . ' — credits: ' . (int) get_user_meta( $u->ID, self::CREDITS, true ) . '</option>';
		}
		echo '</select> ';
		submit_button( 'Add 1 credit', 'secondary', 'submit', false );
		echo '</form>';

		/* ---- scans -------------------------------------------------------- */
		echo '<h2 style="margin-top:28px">Scans</h2><table class="widefat striped"><thead><tr><th>ID</th><th>Client</th><th>Status</th><th>BF%</th><th>Created</th><th>Detail</th></tr></thead><tbody>';
		if ( ! $rows ) { echo '<tr><td colspan="6">No scans yet.</td></tr>'; }
		foreach ( (array) $rows as $r ) {
			$u      = get_user_by( 'id', $r->user_id );
			$res    = $r->result ? json_decode( $r->result, true ) : array();
			$detail = 'failed' === $r->status ? esc_html( (string) $r->fail_reason )
				: ( isset( $res['mode'] ) ? esc_html( $res['mode'] . ' mode' ) : '—' );
			echo '<tr><td>' . (int) $r->id . '</td>'
				. '<td>' . esc_html( $u ? $u->display_name : '#' . $r->user_id ) . '</td>'
				. '<td>' . esc_html( $r->status ) . '</td>'
				. '<td>' . esc_html( isset( $res['bf_percent'] ) ? $res['bf_percent'] . '%' : '—' ) . '</td>'
				. '<td>' . esc_html( $r->created_at ) . '</td>'
				. '<td>' . $detail . '</td></tr>';
		}
		echo '</tbody></table>';

		/* ---- self-test script --------------------------------------------- */
		?>
		<script>
		(function () {
			var btn = document.getElementById('fbf-selftest');
			var out = document.getElementById('fbf-selftest-out');
			if (!btn) { return; }
			btn.addEventListener('click', function () {
				btn.disabled = true;
				var label = btn.textContent;
				btn.textContent = 'Uploading 12 MB…';
				out.style.display = 'block';
				out.textContent = 'Sending a 12 MB probe file through the real upload path…';
				var bytes = new Uint8Array(12 * 1024 * 1024);
				for (var i = 0; i < bytes.length; i += 4096) { bytes[i] = i & 255; }
				var fd = new FormData();
				fd.append('probe', new Blob([bytes], { type: 'application/octet-stream' }), 'probe.bin');
				fetch('<?php echo esc_js( rest_url( self::NS . '/bodyscan/selftest' ) ); ?>', {
					method: 'POST',
					credentials: 'include',
					headers: { 'X-WP-Nonce': '<?php echo esc_js( wp_create_nonce( 'wp_rest' ) ); ?>' },
					body: fd
				}).then(function (r) {
					return r.text().then(function (t) { return { s: r.status, t: t }; });
				}).then(function (r) {
					var msg;
					try {
						var j = JSON.parse(r.t);
						msg = (j.probe && j.probe.ok)
							? 'PASS — the server accepted a ' + j.probe.received + ' byte upload.\n\n'
							: 'FAIL — ' + ((j.probe && j.probe.why) || j.message || 'see details') + '\n\n';
						msg += JSON.stringify(j, null, 2);
					} catch (e) {
						msg = 'HTTP ' + r.s + '\n' + r.t.slice(0, 2000);
					}
					out.textContent = msg;
				}).catch(function (e) {
					out.textContent = 'Request failed: ' + e;
				}).then(function () {
					btn.disabled = false;
					btn.textContent = label;
				});
			});
		})();
		</script>
		<?php
		echo '</div>';
	}

	public static function save_settings() {
		if ( ! current_user_can( 'manage_options' ) ) { wp_die( 'Admins only.' ); }
		check_admin_referer( 'fbf_bodyscan_settings' );
		update_option( 'fbf_bodyscan_pay_url_1', esc_url_raw( (string) ( $_POST['pay1'] ?? '' ) ) );
		update_option( 'fbf_bodyscan_pay_url_5', esc_url_raw( (string) ( $_POST['pay5'] ?? '' ) ) );
		wp_safe_redirect( admin_url( 'admin.php?page=fbf-bodyscan&saved=1' ) );
		exit;
	}

	public static function grant_credit() {
		if ( ! current_user_can( 'manage_options' ) ) { wp_die( 'Admins only.' ); }
		check_admin_referer( 'fbf_bodyscan_credit' );
		$uid = (int) ( $_POST['user_id'] ?? 0 );
		if ( $uid ) {
			$c = (int) get_user_meta( $uid, self::CREDITS, true );
			update_user_meta( $uid, self::CREDITS, $c + 1 );
		}
		wp_safe_redirect( admin_url( 'admin.php?page=fbf-bodyscan&credited=1' ) );
		exit;
	}

	public static function fix_ini_action() {
		if ( ! current_user_can( 'manage_options' ) ) { wp_die( 'Admins only.' ); }
		check_admin_referer( 'fbf_bodyscan_fixini' );
		$res  = self::write_user_ini();
		$note = ( $res['ok'] ? 'OK: ' : 'Could not write ' . $res['path'] . ' — ' ) . $res['note'];

		// If PHP is still enforcing limits that are too small for a scan video,
		// escalate to .htaccess (self-reverting if the server rejects it).
		if ( ! self::php_limits_ok() ) {
			if ( ! self::user_ini_enabled() ) {
				$note .= ' This server has user_ini.filename disabled, so .user.ini is ignored entirely — escalating to .htaccess.';
			}
			$h     = self::write_htaccess();
			$note .= ' ' . $h['note'];
		}

		set_transient( 'fbf_bodyscan_ini_note', $note, 60 );
		delete_transient( 'fbf_bodyscan_ini_checked' );
		wp_safe_redirect( admin_url( 'admin.php?page=fbf-bodyscan&ini=1' ) );
		exit;
	}
}

FBF_BodyScan::init();
