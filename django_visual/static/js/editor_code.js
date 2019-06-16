// Visual Django IDE - Utils to work with code files

function load_file(path, el) {
	var content = "";
	var tid = el;

	$.get("/ide/open_file/", {"path": path}, function(data) {
		//console.log(data);
		$("#code-editor-" + el).text(data);
		
		var PythonMode = ace.require("ace/mode/python").Mode;
		var editor = ace.edit("code-editor-" + el);

		editor.setTheme("ace/theme/monokai");
		editor.session.setMode(new PythonMode());
		editor.setFontSize(14);

		editor.getSession().on("change", function () {
		    $("#active_editor").val(editor.getSession().getValue());
		    
		    var label = $("#tab-" + tid + " span").text();
		    
		    if (!label.endsWith(" * ")) {
		    	$("#tab-" + tid + " span").text(label + " * ");
		    	$("#tab-" + tid + " span").after(
		    		'<i class="glyphicon glyphicon-save save-tab" data-panel="' + tid + '">&nbsp;</i>'
		    	);
		    }

		});
	});
}