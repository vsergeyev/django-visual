// Visual Django IDE - Utils to work with IDE UI

function project_tree_open_file(label, path) {
	var is_open_already = false;

	$("#center_column_tabs a.nav-link").each(function() {
		if ( $(this).attr("data-path") == path ) {
			is_open_already = true;
			$(this).tab("show");
		}
	});

	if (is_open_already)
		return;

	var ts = + new Date();

	$('<li class="nav-item">'
	  + '<a href="#editor-' + ts + '" class="nav-link bg-light" id="tab-' + ts + '" data-toggle="tab" role="tab" '
	  + 'data-path="' + path + '"><span>' + label
	  + '</span> <i class="glyphicon glyphicon-close close-tab" data-panel="' + ts + '">&nbsp;</i></a>'
		  + '</li>').appendTo("#center_column_tabs");

	$('<div class="tab-pane h-100" id="editor-' + ts + '" role="tabpanel">'
	  + '<div class="code-editor" id="code-editor-' + ts + '"></div>'
	  + '</div>').appendTo('#center_column_tabs_content');

	$('#tab-' + ts).tab('show');

	if (label.endsWith(".sqlite3")) {
		load_db(path, 'code-editor-' + ts);

	} else if (label.endsWith("models.py")) {
		load_file(path, ts);

	} else {
		load_file(path, ts);
	};
}

function project_tree_save_file(path) {
	var content = $("#active_editor").val();

	$.post("/ide/save_file/", {"path": path, "content": content}, function(data) {
		console.log(data);
	});
}