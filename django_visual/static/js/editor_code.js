// Visual Django IDE - Utils to work with code files

function load_file(path, el) {
	var content = "";

	$.get("/ide/open_file/", {"path": path}, function(data) {
		//console.log(data);
		$("#" + el).text(data);
		
		var PythonMode = ace.require("ace/mode/python").Mode;
		var editor = ace.edit(el);

		editor.setTheme("ace/theme/monokai");
		editor.session.setMode(new PythonMode());
		editor.setFontSize(14);
	});
}