package org.robotframework.formslibrary.keyword;
import java.util.ArrayList;
import java.util.List;
import java.awt.Component;

import org.robotframework.formslibrary.context.ContextChangeMonitor;
import org.robotframework.formslibrary.operator.LabelOperator;
import org.robotframework.formslibrary.operator.TextFieldOperatorFactory;
import org.robotframework.formslibrary.operator.TextFieldOperator;
import org.robotframework.formslibrary.operator.TableOperator;
import org.robotframework.javalib.annotation.ArgumentNames;
import org.robotframework.javalib.annotation.RobotKeyword;
import org.robotframework.javalib.annotation.RobotKeywords;
import org.robotframework.javalib.annotation.RobotKeywordOverload;

@RobotKeywords
public class TextFieldKeywords {

	@RobotKeyword("Locate a field by name and set it to the given value. ':' in the field labels are ignored.\n\n" + "Example:\n"
			+ "| Set Field | _username_ | _jeff_ | \n")
	@ArgumentNames({ "identifier", "value" })
	public void setField(String identifier, String value) {
		TextFieldOperatorFactory.getOperator(identifier).setValue(value);
	}

	@RobotKeyword("Locate a field by a label on the same height to the left of the text field. ':' in the field labels are ignored.\n"
			+ "Should only be used for fields which do not have a link with the label\n\n" + "Example:\n"
			+ "| Set Field Next To Label | _username_ | _jeff_ | \n")
	@ArgumentNames({ "identifier", "value" })
	public void setFieldNextToLabel(String identifier, String value) {
		LabelOperator label = new LabelOperator(identifier);
		TextFieldOperatorFactory.getOperator(label).setValue(value);
	}

	@RobotKeyword("Verify field content. This check cannot be used for repeated table fields. For verifying a field in a table use Select Row instead.\n\n"
			+ "Example:\n" + "| Field Should Contain | _username_ | _jeff_ | \n")
	@ArgumentNames({ "identifier", "value" })
	public void verifyField(String identifier, String value) {
		TextFieldOperatorFactory.getOperator(identifier).verifyValue(value);
	}

	@RobotKeyword("Get field content.\n\n" + "Example:\n" + "| \n" + "| ${textFieldValue}= | Get Field | _username_ | \n")
	@ArgumentNames({ "identifier" })
	public String getField(String identifier) {
		return TextFieldOperatorFactory.getOperator(identifier).getValue();
	}

	@RobotKeyword("Locate a field by a label on the same height to the left of the text field. ':' in the field labels are ignored.\n"
			+ "Should only be used for fields which do not have a link with the label\n\n" + "Example:\n"
			+ "| Get Field Next To Label | _username_ | | \n")
	@ArgumentNames({ "identifier" })
	public String getFieldNextToLabel(String identifier) {
		LabelOperator label = new LabelOperator(identifier);
		return TextFieldOperatorFactory.getOperator(label).getValue();
	}

	@RobotKeyword("Uses current context to search for a textfield by its label and when found, pushes it.\n\n "
			+ " If the button opens a new window and detectWindowChange=true, the context will be set to the new window automatically. "
			+ "Similarly if the button closes a window, the context will be reset to the root context. DetectWindowChange defaults to true. Example:\n | Click Text Field | _OK_ |\n")
	@ArgumentNames({ "identifier", "detectWindowChange=" })
	public void clickTextField(String identifier, boolean detectWindowChange) {

		if (detectWindowChange) {
			ContextChangeMonitor monitor = new ContextChangeMonitor();
			monitor.start();
			new TextFieldOperator(identifier).push();
			monitor.stop();
		} else {
			new TextFieldOperator(identifier).push();
		}
	}

	@RobotKeywordOverload
	public void clickTextField(String identifier) {
		clickTextField(identifier, true);
	}

	@RobotKeyword("Find text field elements which match the given string")
	@ArgumentNames({ "text" })
	public List<String> findTextFields(String text) {
		List<Component> components =  new TableOperator().findTextFieldsByValue(text);

		List<String> results = new ArrayList<String>();
		for (Component component: components) {
			results.add(component.getName());
		}
		return results;
	}

}
